#!/usr/bin/env python3
"""Position difference to A0 over time (max over x, y, z), per config, every --step vblanks.

Usage:
  python diff_time.py <run>/move.json [--step 10] [--shift 1]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tools/bench'))
import move_compare as mc  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run')
    ap.add_argument('--step', type=int, default=10)
    ap.add_argument('--shift', type=int, default=1)
    a = ap.parse_args()
    with open(a.run, encoding='utf-8') as fh:
        groups = mc.series(json.load(fh))
    for key, runs in sorted(groups.items(), key=lambda kv: str(kv[0])):
        A = runs['A0']
        others = [c for c in runs if c != 'A0']
        print('gap/angle', key, 'v', *others)
        for v in range(0, max(A) + 1, a.step):
            if v not in A:
                continue
            row = []
            for c in others:
                C = runs[c]
                row.append(round(max(abs(A[v][i] - C[v - a.shift][i]) for i in range(3)), 4) if v - a.shift in C else None)
            print(v, *row)


if __name__ == '__main__':
    main()
