#!/usr/bin/env python3
"""Fire cadence of the equipped weapon, in emulated time (no owner needed).

Holds or taps the fire button, frame-locked (tools/bench/breakloop.py: input
changes only at game frame boundaries, timed in emulated vblanks), and
timestamps every ammo decrement with a memory write breakpoint on the weapon's
stock. The CPU stops before the store; the new value comes from the store's
source register, so each shot gets its own CoreTiming tick. Emulated time makes
the result independent of host speed, window focus or throttling (the failure
mode of runs 85-91 in CURRENT_STATE.md), and breakpoints avoid the polling that
starves PPSSPP. The first press is the time origin (firstShotDelay*).

Addresses (LEVEL_01 module RVAs, tools/runtime/set-ammo.py):
  player            0x337940, equipped weapon id at player+0x998
  ammo entry        0x2AE95C + id * 0x58, stock (int) at +0x40
Constants: CPU clock 222 MHz, measured with tools/bench/clock.py (2026-10-19).

Usage:
  python tools/bench/fire_rate.py --seconds 8 --label C1 --out D:/racsm60fps/work/runs/fire-c1-001
  python tools/bench/fire_rate.py --mode tap --tap-vblanks 2 --label A0-tap --out <dir>
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa: E402
from breakloop import BreakLoop, CPU_HZ  # noqa: E402

VBLANK_TICKS = 3_703_700         # one 59.94 Hz vblank at 222 MHz (1001/60000 s)
FRAME_30 = 1001 / 30000          # one A0 frame (two vblanks), seconds
PLAYER, WEAPON_ID, AMMO_BASE, AMMO_STRIDE, RANK, STOCK = 0x337940, 0x998, 0x2AE95C, 0x58, 0x3C, 0x40
LEVEL01_SIZE = 0x46B900
SUMMARY_KEYS = ('label', 'mode', 'weaponId', 'shots', 'shotsPerSecond', 'gapSecondsMedian',
                'firstShotDelayVblanks', 'consumedAfterWindow', 'frames')


def set_rank(d, rank):
    """TEST AID: write the equipped weapon's rank (0 = V1) in the level copy (+0x3C,
    layout in tools/runtime/inventory-aid.py). RAM only, after a state load; the
    save copy and the savestate are untouched. The fire cadence follows at once
    (OBSERVED 2026-10-19); models and other rank parameters are not reloaded."""
    base = d.module('rcp1')['address']
    wid = d.u32(base + PLAYER + WEAPON_ID)
    addr = base + AMMO_BASE + wid * AMMO_STRIDE + RANK
    d.pause()
    try:
        old = d.u32(addr)
        d.write_u32(addr, rank, expect=old)
    finally:
        d.resume()
    return old


def measure(d, seconds, button='circle', mode='hold', tap_vblanks=2):
    """Hold, or tap (pressed `tap_vblanks`, released `tap_vblanks`), frame-locked from the first frame."""
    mod = d.module('rcp1')
    if mod['size'] != LEVEL01_SIZE:
        raise SystemExit('LEVEL_01 (Pokitaru) must be resident')
    base = mod['address']
    wid = d.u32(base + PLAYER + WEAPON_ID)
    if not 0 <= wid < 0x19:
        raise SystemExit(f'bad weapon id {wid}')
    stock_addr = base + AMMO_BASE + wid * AMMO_STRIDE + STOCK
    rec = {'weaponId': wid, 'stockRva': hex(stock_addr - base), 'cpuHz': CPU_HZ, 'mode': mode,
           'stockBefore': d.u32(stock_addr)}
    if mode == 'tap':
        rec['tapVblanks'] = tap_vblanks
    shots, presses = [], []
    state = {'t0': None, 'down': None}

    def on_frame(t, value):
        if value is None:                         # run start, not a frame boundary: wait for one
            return
        if state['t0'] is None:
            state['t0'] = t
        if mode == 'hold':
            down = True
        else:                                     # phase in whole vblanks, robust to jitter inside a frame
            down = (round((t - state['t0']) / VBLANK_TICKS) // tap_vblanks) % 2 == 0
        if down != state['down']:
            d.buttons(**{button: down})
            state['down'] = down
            if down:
                presses.append(t)

    def on_stock(t, old, new):
        if new < old:
            shots.extend([t] * (old - new))

    loop = BreakLoop(d, base)
    loop.watch(stock_addr, on_stock)
    loop.every_frame(on_frame)
    loop.at_end(lambda: d.buttons(**{button: False}))
    t_start, t_end = loop.run(seconds)
    time.sleep(0.3)
    t0 = state['t0']
    after = d.u32(stock_addr)
    rec.update(stockAfter=after, consumedAfterWindow=rec['stockBefore'] - after - len(shots),
               pendingShotAtEnd=loop.pending_at_end is not None,
               breaks=loop.breaks, frames=loop.frames, otherBreaks=loop.other, presses=len(presses),
               shots=len(shots), shotTicks=[t - t0 for t in shots],
               shotsPerEmulatedSecond=round(len(shots) / ((t_end - t0) / CPU_HZ), 3))
    if shots:
        rec['firstShotDelaySeconds'] = round((shots[0] - t0) / CPU_HZ, 4)
        rec['firstShotDelayVblanks'] = round((shots[0] - t0) / VBLANK_TICKS, 2)
    if len(shots) >= 2:
        window = (shots[-1] - shots[0]) / CPU_HZ
        gaps = [(b - a) / CPU_HZ for a, b in zip(shots, shots[1:])]
        rec.update(windowSeconds=round(window, 5), shotsPerSecond=round((len(shots) - 1) / window, 3),
                   gapSecondsMedian=round(sorted(gaps)[len(gaps) // 2], 5),
                   gapFrames30=[round(g / FRAME_30, 2) for g in gaps])
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--seconds', type=float, default=8.0, help='emulated seconds of fire input')
    ap.add_argument('--button', default='circle')
    ap.add_argument('--mode', choices=('hold', 'tap'), default='hold')
    ap.add_argument('--tap-vblanks', type=int, default=2, help='tap: vblanks pressed, then as many released')
    ap.add_argument('--label', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    with Debugger(a.port).connect() as d:
        rec = {'label': a.label, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               **measure(d, a.seconds, a.button, a.mode, a.tap_vblanks)}
    (a.out / 'fire-rate.json').write_text(json.dumps(rec, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: rec.get(k) for k in SUMMARY_KEYS}))


if __name__ == '__main__':
    main()
