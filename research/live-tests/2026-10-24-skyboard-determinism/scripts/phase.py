"""Pre-GO history of rec.py runs: first frame, GO frame, ticks, countdown and recorded words.
python phase.py RUN [RUN ...]

Absolute ticks (CoreTiming) are restored by the state load, so runs from the same state share
the tick axis: GO ticks and frame phases are comparable across runs."""
import json, sys

R = 'D:/sandboxes/racsm60fps/work/runs/'
VB = 222_000_000 / (60000 / 1001)   # one 59.94 Hz vblank at 222 MHz, in ticks


def load(name):
    m = json.load(open(R + name + '/samples.json'))
    s = m['samples']
    gi = next(i for i, x in enumerate(s) if x['raceFrames'] > 0)
    return m, s, gi


rows = []
for name in sys.argv[1:]:
    m, s, gi = load(name)
    f, g = s[0], s[gi]
    gaps = [s[i + 1]['t'] - s[i]['t'] for i in range(min(gi, 40))]
    print(f"== {name} config={m['config']} applied={m.get('applied')}")
    print(f"  first: v={f['v']} frame={f['frame']} t={f['t']} countdown={f['countdown']} clock={f['clock']:.6f} t29E588={f['t29E588']:.6f}")
    print(f"  GO   : v={g['v']} frame={g['frame']} t={g['t']} countdown={g['countdown']} clock={g['clock']:.6f} t29E588={g['t29E588']:.6f}")
    print(f"  frames first->GO {g['frame'] - f['frame']}, ticks {g['t'] - f['t']} = {(g['t'] - f['t']) / VB:.3f} vb")
    print(f"  first gaps (vb): {[round(x / VB, 3) for x in gaps[:8]]}")
    for k in range(0, 6):
        x = s[gi + k]
        print(f"  GO+{k}: frame={x['frame']} t={x['t']} pos={x['pos']} rf={x['raceFrames']} hud={x['hud']:.4f} clock={x['clock']:.6f} t29E588={x['t29E588']:.6f}")
    rows.append((name, g))
if len(rows) == 2:
    (na, ga), (nb, gb) = rows
    dt = gb['t'] - ga['t']
    print(f"GO tick difference {dt} = {dt / VB:.4f} vb; frame-number difference {gb['frame'] - ga['frame']}")
