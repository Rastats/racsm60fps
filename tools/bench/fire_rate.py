#!/usr/bin/env python3
"""Fire cadence of the equipped weapon, in emulated time (no owner needed).

Holds the fire button through the debugger and timestamps every ammo
decrement with a memory write breakpoint on the weapon's stock: the CPU stops
on the write, the `cpu.stepping` broadcast carries the exact CoreTiming tick
count, the script resumes. Emulated time makes the result independent of host
speed, window focus or throttling (the failure mode of runs 85-91 in
CURRENT_STATE.md), and the breakpoint avoids the polling that starves PPSSPP.

Addresses (LEVEL_01 module RVAs, tools/runtime/set-ammo.py):
  player            0x337940, equipped weapon id at player+0x998
  ammo entry        0x2AE95C + id * 0x58, stock (int) at +0x40
Constants: CPU clock 222 MHz, measured with tools/bench/clock.py (2026-10-19).

Usage:
  python tools/bench/fire_rate.py --seconds 8 --label C1 --out D:/racsm60fps/work/runs/fire-c1-001
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa: E402

CPU_HZ = 222_000_000
FRAME_30 = 1001 / 30000          # one A0 frame (two 59.94 Hz vblanks), seconds
PLAYER, WEAPON_ID, AMMO_BASE, AMMO_STRIDE, STOCK = 0x337940, 0x998, 0x2AE95C, 0x58, 0x40
LEVEL01_SIZE = 0x46B900


def measure(d, seconds, button='circle'):
    mod = d.module('rcp1')
    if mod['size'] != LEVEL01_SIZE:
        raise SystemExit('LEVEL_01 (Pokitaru) must be resident')
    base = mod['address']
    wid = d.u32(base + PLAYER + WEAPON_ID)
    if not 0 <= wid < 0x19:
        raise SystemExit(f'bad weapon id {wid}')
    stock_addr = base + AMMO_BASE + wid * AMMO_STRIDE + STOCK
    rec = {'weaponId': wid, 'stockRva': hex(stock_addr - base), 'cpuHz': CPU_HZ}
    last = d.u32(stock_addr)
    rec['stockBefore'] = last
    span = int(seconds * CPU_HZ)
    shots, breaks = [], 0
    d.add_mem_breakpoint(stock_addr, 4, write=True, change=True)
    stepping = False
    try:
        d.buttons(**{button: True})
        t_start = int(d.cpu()['ticks'])
        wall_deadline = time.monotonic() + max(60.0, seconds * 30)
        while time.monotonic() < wall_deadline:
            ev = d.wait_event('cpu.stepping', timeout=1.0)
            if ev is None:
                if int(d.cpu()['ticks']) - t_start >= span:
                    break
                continue
            stepping = True
            breaks += 1
            t = int(ev['ticks'])
            s = d.u32(stock_addr)
            if s < last:
                shots.extend([t] * (last - s))
            last = s
            if t - t_start >= span:
                break
            d.resume_quiet()
            stepping = False
        d.buttons(**{button: False})
    finally:
        d.remove_mem_breakpoint(stock_addr, 4)
        try:
            d.buttons(**{button: False})
        finally:
            if stepping or d.cpu().get('stepping'):
                d.resume()
    rec.update(stockAfter=last, breaks=breaks, shotTicks=[t - t_start for t in shots])
    if len(shots) >= 2:
        window = (shots[-1] - shots[0]) / CPU_HZ
        gaps = [(b - a) / CPU_HZ for a, b in zip(shots, shots[1:])]
        rec.update(shots=len(shots), windowSeconds=round(window, 5),
                   shotsPerSecond=round((len(shots) - 1) / window, 3),
                   gapSecondsMedian=round(sorted(gaps)[len(gaps) // 2], 5),
                   gapFrames30=[round(g / FRAME_30, 2) for g in gaps],
                   firstShotDelaySeconds=round((shots[0] - t_start) / CPU_HZ, 4))
    else:
        rec['shots'] = len(shots)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--seconds', type=float, default=8.0, help='emulated seconds to hold fire')
    ap.add_argument('--button', default='circle')
    ap.add_argument('--label', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    with Debugger(a.port).connect() as d:
        rec = {'label': a.label, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               **measure(d, a.seconds, a.button)}
    (a.out / 'fire-rate.json').write_text(json.dumps(rec, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: rec.get(k) for k in ('label', 'weaponId', 'shots', 'shotsPerSecond',
                                              'gapSecondsMedian', 'firstShotDelaySeconds', 'breaks')}))


if __name__ == '__main__':
    main()
