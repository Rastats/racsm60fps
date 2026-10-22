#!/usr/bin/env python3
"""A/B/C fire-cadence comparison from a fixed savestate (unattended).

For each configuration: load the named savestate (restores the original code
and the ammo stock), wait for the state to settle, apply the configuration
with tools/bench/wordfix.py, then hold fire and timestamp shots with
tools/bench/fire_rate.py. Every configuration therefore starts from the same
emulated state. Results: <out>/abc-fire.json and one line per configuration.

Usage:
  python tools/bench/abc_fire.py --state pokitaru-start --seconds 6 \
      --configs A0 C1 C1+weapondt --out D:/racsm60fps/work/runs/abc-fire-001
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa: E402
import states  # noqa: E402
import wordfix  # noqa: E402
import fire_rate  # noqa: E402


def parse(config):
    core, *fixes = config.split('+')
    if core not in ('A0', 'C1'):
        raise SystemExit(f'bad config {config}: must start with A0 or C1')
    return core, set(fixes)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--state', required=True)
    ap.add_argument('--seconds', type=float, default=6.0)
    ap.add_argument('--settle', type=float, default=1.0, help='wall seconds after loading the state')
    ap.add_argument('--configs', nargs='+', required=True)
    ap.add_argument('--mode', choices=('hold', 'tap'), default='hold')
    ap.add_argument('--tap-vblanks', type=int, default=2)
    ap.add_argument('--rank', type=int, help='TEST AID: weapon rank written after each state load (0 = V1)')
    ap.add_argument('--weapon', type=int, help='TEST AID: weapon id requested after each state load '
                    '(fire_rate.request_weapon); refused ids fall back to the Blaster')
    ap.add_argument('--repeat', type=int, default=1)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    results = []
    for rep in range(a.repeat):
        for config in a.configs:
            core, fixes = parse(config)
            states.load(a.state)
            time.sleep(a.settle)
            with Debugger(a.port).connect() as d:
                d.release_all()
                if a.weapon is not None:
                    equipped = fire_rate.request_weapon(d, a.weapon)
                    if equipped != a.weapon:
                        raise SystemExit(f'weapon {a.weapon} refused by the game (equipped {equipped})')
                applied = wordfix.apply(d, core, fixes)
                rank_before = fire_rate.set_rank(d, a.rank) if a.rank is not None else None
                rec = fire_rate.measure(d, a.seconds, mode=a.mode, tap_vblanks=a.tap_vblanks)
            row = {'config': config, 'repeat': rep, 'writes': len(applied['writes']),
                   'jitRefresh': applied['jitRefresh'], 'rank': a.rank, 'rankInState': rank_before, **rec}
            results.append(row)
            print(json.dumps({'config': config, 'repeat': rep,
                              **{k: row.get(k) for k in fire_rate.SUMMARY_KEYS[1:]}}), flush=True)
    (a.out / 'abc-fire.json').write_text(json.dumps({'state': a.state, 'seconds': a.seconds, 'mode': a.mode,
                                                     'results': results}, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
