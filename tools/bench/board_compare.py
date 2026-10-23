#!/usr/bin/env python3
"""Compare board_probe.py runs: metrics at equal times after GO, gap to A0, repeat check.

For each config and side, prints the metrics of board_probe at each time of
TIMES_S, the gap of C-configs to A0 (absolute and in %), and whether repeats
of a config gave identical post-GO samples (positions and words, bit for bit).
Rates of the timers are given per emulated second over [0.5, 4.9] s after GO.

Usage:
  python tools/bench/board_compare.py <root>/work/runs/banc-sky-straight-002/board.json [--json out.json]
"""
import argparse
import json
from pathlib import Path

KEYS = ('path', 'speedUps', 'hudSpeed', 'headingDeg', 'y', 'raceFrames', 'countdown',
        'clock227D04', 'timer29E588', 'player574')
RATE_KEYS = ('raceFrames', 'clock227D04', 'timer29E588', 'player574', 'hudSpeed')


def post_go(r):
    return [(s['pos'], {k: s[k] for k in s if k not in ('t', 'v', 'frame', 'pos')}, s['t'] - r['go'])
            for s in r['samples'] if s['t'] >= r['go']]


def summary(results):
    groups = {}
    for r in results:
        groups.setdefault((r['config'], r['side']), []).append(r)
    out = {}
    for (config, side), rs in groups.items():
        first = rs[0]['metrics']
        same = all(post_go(r) == post_go(rs[0]) for r in rs[1:])
        at = first['atS']
        t0, t1 = '0.5', '4.9'
        rates = {k: round((at[t1][k] - at[t0][k]) / 4.4, 4) for k in RATE_KEYS
                 if at[t1].get(k) is not None and at[t0].get(k) is not None}
        cds = [r['metrics'].get('countdownFromStartToGoS') for r in rs if r['metrics'].get('countdownFromStartToGoS')]
        out[f'{config}|{side}'] = {'config': config, 'side': side, 'repeats': len(rs), 'repeatsIdentical': same,
                                   'countdownToGoS': cds, 'ratesPerS': rates, 'atS': at}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board', type=Path, nargs='+')
    ap.add_argument('--json', type=Path)
    a = ap.parse_args()
    results = []
    for p in a.board:
        results += json.loads(p.read_text(encoding='utf-8'))['results']
    out = summary(results)
    for key, g in out.items():
        ref = out.get(f'A0|{g["side"]}')
        print(f'== {g["config"]} side={g["side"]} repeats={g["repeats"]} identical={g["repeatsIdentical"]} '
              f'countdown->GO {g["countdownToGoS"]} rates/s {g["ratesPerS"]}')
        for ts, row in g['atS'].items():
            cells = []
            for k in KEYS:
                v = row.get(k)
                if v is None:
                    continue
                cell = f'{k}={v}'
                if ref and g['config'] != 'A0' and isinstance(v, (int, float)) and ref['atS'][ts].get(k) is not None:
                    r0 = ref['atS'][ts][k]
                    if k == 'headingDeg':       # angle gap, wrapped to [-180, 180)
                        cell += f'({(v - r0 + 180) % 360 - 180:+.4g} deg)'
                    else:
                        cell += f'({v - r0:+.4g}{"" if not r0 else f", {100 * (v - r0) / abs(r0):+.1f}%"})'
                cells.append(cell)
            print(f'  t={ts}s ' + ' '.join(cells))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
