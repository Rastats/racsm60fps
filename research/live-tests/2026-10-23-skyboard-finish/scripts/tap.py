"""D-pad up double-tap window test on LEVEL_22 (0x1056E8): accepted when 0x24064C is 0 after the 2nd press.

python tap.py --state banc-skyboard-arrive --config A0 --gaps 8,20,40,56,64 --out FILE.json
Each test: press up HOLD vblanks, release GAP vblanks, press up HOLD vblanks, release; read 0x24064C
and 0x240648 SETTLE vblanks later; IDLE vblanks between tests.
"""
import argparse, json, struct, sys, time
from pathlib import Path
BENCH = Path('D:/sandboxes/racsm60fps/wt-banc/tools/bench')
sys.path.insert(0, str(BENCH))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa
from breakloop import BreakLoop  # noqa
import states, wordfix, levels  # noqa

VB = 3_703_700
HOLD, SETTLE, IDLE = 6, 12, 120
ap = argparse.ArgumentParser()
ap.add_argument('--state', required=True)
ap.add_argument('--config', default='A0')
ap.add_argument('--gaps', default='8,20,40,56,64')
ap.add_argument('--out', type=Path, required=True)
a = ap.parse_args()
gaps = [int(g) for g in a.gaps.split(',')]
if a.state != '-':
    states.load(a.state)
    time.sleep(1.0)
with Debugger(DEFAULT_PORT).connect() as d:
    d.release_all()
    core, *fx = a.config.split('+')
    applied = wordfix.apply(d, core, set(fx))
    base, prof = levels.profile(d)

    def i32(rva):
        return struct.unpack('<i', d.read(base + rva, 4))[0]

    # schedule (relative to start vblank S): (v, action, test index)
    sched, t0, start, results, trace = [], [], [], [], []
    v = 0
    for k, g in enumerate(gaps):
        sched += [(v, 'down', k), (v + HOLD, 'up', k), (v + HOLD + g, 'down2', k),
                  (v + 2 * HOLD + g, 'up2', k), (v + 2 * HOLD + g + SETTLE, 'read', k)]
        v += 2 * HOLD + g + SETTLE + IDLE
    total = v

    def on_frame(t, value):
        if value is None:
            return
        if not t0:
            t0.append(t)
        v = round((t - t0[0]) / VB)
        rf = i32(0x240658)
        if not start:
            if rf < 90:          # wait for the race to run (counter starts at GO)
                return
            start.append(v)
            results.append({'startV': v, 'startCount': rf})
        rel = v - start[0]
        trace.append([rel, rf, i32(0x240648), i32(0x24064C)])
        while sched and sched[0][0] <= rel:
            _, act, k = sched.pop(0)
            if act in ('down', 'down2'):
                d.buttons(up=True)
                results.append({'test': k, 'gap': gaps[k], act: rel, 'count': rf})
            elif act in ('up', 'up2'):
                d.buttons(up=False)
                results.append({'test': k, act: rel, 'count': rf})
            else:
                results.append({'test': k, 'gap': gaps[k], 'read': rel, 'count': rf,
                                'last': i32(0x240648), 'button': i32(0x24064C),
                                'accepted': i32(0x24064C) == 0})
        return not sched

    loop = BreakLoop(d, base)
    loop.every_frame(on_frame)
    loop.at_end(lambda: d.release_all())
    loop.run(total / 60 + 20, wall_limit=(total / 60 + 20) * 60)
a.out.write_text(json.dumps({'config': a.config, 'applied': applied['fixes'], 'writes': len(applied['writes']),
                             'results': results, 'trace': trace}) + '\n')
for r in results:
    if 'read' in r:
        print(a.config, 'gap', r['gap'], 'accepted' if r['accepted'] else 'refused', r)
