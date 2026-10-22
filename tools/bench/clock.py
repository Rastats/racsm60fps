#!/usr/bin/env python3
"""Measure the emulated clock: game frames versus PPSSPP CoreTiming ticks.

`cpu.status.ticks` counts emulated CPU cycles. With the game frame counter
(LEVEL module RVA 0x2AF28C, +1 per main-loop frame, docs/DECOMPILATION_FINDINGS.md)
this gives ticks per game frame, hence the emulated frame rate once the CPU
clock is known. The PSP display refreshes at 60000/1001 Hz (59.94 Hz); the
original game (A0) waits two vblanks per frame, so a steady A0 run yields
29.97 frames per emulated second and fixes the clock:
    cpu_hz = ticks_per_frame * 29.97.

Usage:
  python tools/bench/clock.py --seconds 10
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa: E402
import levels  # noqa: E402

FRAME_COUNTER_RVA = 0x2AF28C
VBLANK_HZ = 60000 / 1001


def sample(d, base, fc_rva=FRAME_COUNTER_RVA):
    t = int(d.cpu()['ticks'])
    f = d.u32(base + fc_rva)
    return t, f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--seconds', type=float, default=10.0, help='wall-clock sampling span')
    ap.add_argument('--interval', type=float, default=0.5)
    a = ap.parse_args()
    with Debugger(a.port).connect() as d:
        mod = d.module('rcp1')
        base = mod['address']
        fc_rva = levels.profile_for_size(mod['size'])['frame_counter']
        pts = [sample(d, base, fc_rva)]
        end = time.monotonic() + a.seconds
        while time.monotonic() < end:
            time.sleep(a.interval)
            pts.append(sample(d, base, fc_rva))
    per_frame = [(t1 - t0) / (f1 - f0) for (t0, f0), (t1, f1) in zip(pts, pts[1:]) if f1 > f0]
    dt = pts[-1][0] - pts[0][0]
    df = pts[-1][1] - pts[0][1]
    tpf = dt / df if df else float('nan')
    print(json.dumps({
        'module': {'base': hex(base), 'size': hex(mod['size'])},
        'samples': len(pts), 'ticks': dt, 'frames': df,
        'ticksPerFrame': round(tpf, 1),
        'ticksPerFrameMedian': round(statistics.median(per_frame), 1) if per_frame else None,
        'ticksPerFrameSpread': [round(min(per_frame), 1), round(max(per_frame), 1)] if per_frame else None,
        'impliedCpuHzIfA0': round(tpf * VBLANK_HZ / 2) if df else None,
        'impliedCpuHzIfC1': round(tpf * VBLANK_HZ) if df else None,
    }, indent=1))


if __name__ == '__main__':
    main()
