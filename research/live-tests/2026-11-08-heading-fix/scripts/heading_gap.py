#!/usr/bin/env python3
"""Heading gap to A0 over the first second of a move_probe walk, per angle and config.

Uses move_compare.py's heading (atan2(dx, dz) per 2 vblanks, C-configs shifted
one vblank). Reports the max |gap| for v in [2, --until] and the gap at a few
vblanks. Rows where either side moved < 1e-4 u are skipped.

Usage:
  python heading_gap.py <run>/move.json [--until 60]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tools/bench'))
import move_compare as mc  # noqa: E402


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run')
    ap.add_argument('--until', type=int, default=60, help='last vblank of the window (60 = 1.0 s)')
    ap.add_argument('--shift', type=int, default=1)
    ap.add_argument('--at', type=int, nargs='+', default=[12, 32, 52, 60])
    a = ap.parse_args()
    with open(a.run, encoding='utf-8') as fh:
        groups = mc.series(json.load(fh))
    for (gap, angle), runs in sorted(groups.items(), key=lambda kv: str(kv[0])):
        A = runs.get('A0')
        if not A:
            continue
        for c in (c for c in runs if c != 'A0'):
            gaps = {}
            for v in range(2, a.until + 1, 2):
                ha, _ = mc.heading(A, v, v + 2)
                hc, _ = mc.heading(runs[c], v - a.shift, v + 2 - a.shift)
                if ha is not None and hc is not None:
                    gaps[v] = round(wrap(hc - ha), 2)
            worst = max(gaps.items(), key=lambda kv: abs(kv[1])) if gaps else (None, None)
            print(json.dumps({'angle': angle, 'config': c, 'n': len(gaps), 'maxAbsGap': worst[1], 'atV': worst[0],
                              'gapAt': {v: gaps.get(v) for v in a.at}}))


if __name__ == '__main__':
    main()
