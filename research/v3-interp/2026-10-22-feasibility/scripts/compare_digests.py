#!/usr/bin/env python3
"""Leak / determinism check: compare the authoritative entity-span digests of two
interp_proto.py runs started from the same savestate, matched on the G1 gate's
`runs` counter (emulated start points differ by the wall-clock delay of loading).

Usage: python compare_digests.py <run A> <run B>
"""
import json
import sys
from pathlib import Path


def by_runs(run):
    rows = json.loads((Path(run) / 'rows.json').read_text(encoding='utf-8'))
    out = {}
    for r in rows[1:]:      # row 0 is labelled ran=True by construction (no previous counter)
        out.setdefault((r['runs'], r['ran']), r['span_sha1'])
    return out


def main():
    a, b = by_runs(sys.argv[1]), by_runs(sys.argv[2])
    common = sorted(set(a) & set(b))
    same = [k for k in common if a[k] == b[k]]
    diff = [k for k in common if a[k] != b[k]]
    print(json.dumps({'common_renders': len(common), 'identical': len(same), 'different': len(diff),
                      'first_different': diff[:5]}, indent=1))


if __name__ == '__main__':
    main()
