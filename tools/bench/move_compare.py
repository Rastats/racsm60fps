#!/usr/bin/env python3
"""Compare move_probe.py runs against A0 at the same emulated instant.

A0 samples every 2 vblanks (even v), C-configs every vblank. C1 leads A0 by
one vblank (60 Hz input sample, MOVEMENT-REPORT.md of 2026-10-19), so a
C-config sample at v-1 is compared with A0 at v.

Two views:
  diff     max |position difference| over x, y, z, per gap/angle and config
  heading  movement heading (degrees, atan2(dx, dz)) and distance per 2 vblanks

Path length alone hides heading errors: two runs can cover the same path
length in different directions (the 2026-10-19 "0.0005 u" walk figure was a
path-length comparison; the position difference is 0.008 u).

Usage:
  python tools/bench/move_compare.py <run>/move.json [--view heading --step 6]
"""
import argparse
import json
import math
from collections import defaultdict


def series(doc):
    out = defaultdict(dict)
    for r in doc['results']:
        out[(r.get('gap'), r.get('angle'))][r['config']] = {s['v']: s['pos'] for s in r['samples']}
    return out


def heading(S, v0, v1):
    if v0 not in S or v1 not in S:
        return None, None
    dx, dz = S[v1][0] - S[v0][0], S[v1][2] - S[v0][2]
    dist = math.hypot(dx, dz)
    return (round(math.degrees(math.atan2(dx, dz)), 2) if dist > 1e-4 else None), round(dist, 4)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run')
    ap.add_argument('--view', choices=('diff', 'heading'), default='diff')
    ap.add_argument('--step', type=int, default=6, help='heading view: vblanks between rows')
    ap.add_argument('--shift', type=int, default=1, help='vblanks by which C-configs lead A0')
    a = ap.parse_args()
    with open(a.run, encoding='utf-8') as fh:
        groups = series(json.load(fh))
    for (gap, angle), runs in sorted(groups.items(), key=lambda kv: str(kv[0])):
        A = runs.get('A0')
        if not A:
            continue
        others = [c for c in runs if c != 'A0']
        if a.view == 'diff':
            for c in others:
                C = runs[c]
                d = [max(abs(A[v][i] - C[v - a.shift][i]) for i in range(3)) for v in A if v - a.shift in C]
                print(json.dumps({'gap': gap, 'angle': angle, 'config': c, 'n': len(d), 'maxDiff': round(max(d), 4)}))
        else:
            print(f'gap={gap} angle={angle}  v  A0(heading, dist/2vb)  ' + '  '.join(others))
            for v in range(2, max(A) - 2, a.step):
                row = [heading(A, v, v + 2)] + [heading(runs[c], v - a.shift, v + 2 - a.shift) for c in others]
                print(v, *row)


if __name__ == '__main__':
    main()
