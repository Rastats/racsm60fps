#!/usr/bin/env python3
"""Summarise interp_proto.py rows: per tracked entity, how often the drawn and the
authoritative translations change between consecutive renders, the step sizes,
and the speed in units per emulated second (CPU 222 MHz, tools/bench/README.md).

Usage: python analyze_rows.py <run dir> [<run dir> ...]
"""
import json
import math
import sys
from pathlib import Path

CPU_HZ = 222_000_000


def summary(rows, key):
    out = {}
    for field in ('auth', 'drawn'):
        pts = [(r['t'], r[key][field]) for r in rows]
        steps = [math.dist(a[1], b[1]) for a, b in zip(pts, pts[1:])]
        moving = [s for s in steps if s > 1e-6]
        span_s = (pts[-1][0] - pts[0][0]) / CPU_HZ
        out[field] = {
            'renders': len(pts),
            'renders_with_change': len(moving),
            'step_mean': round(sum(moving) / len(moving), 5) if moving else 0.0,
            'step_max': round(max(moving), 5) if moving else 0.0,
            'step_min': round(min(moving), 5) if moving else 0.0,
            'path_per_s': round(sum(steps) / span_s, 4) if span_s else None,
        }
    return out


def main():
    for run in sys.argv[1:]:
        rows = json.loads((Path(run) / 'rows.json').read_text(encoding='utf-8'))
        keys = [k for k in rows[0] if ':' in k]
        span = (rows[-1]['t'] - rows[0]['t']) / CPU_HZ
        print(f'== {run}: {len(rows)} renders over {span:.3f} emulated s '
              f'({(len(rows) - 1) / span:.2f} renders/s)')
        for k in keys:
            print(k, json.dumps(summary(rows, k)))


if __name__ == '__main__':
    main()
