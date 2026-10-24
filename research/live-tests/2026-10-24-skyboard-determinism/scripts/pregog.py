"""Per game frame (frame counter value), compare recorded words of rec.py runs before and after GO.
python pregog.py RUN_A RUN_B [--every N]

Runs from the same state reach GO at the same frame number (185 from banc-skyboard-arrive), so the
frame counter is the common axis; prints the frames where pos, hud or t29E588 differ."""
import json, math, sys

R = 'D:/sandboxes/racsm60fps/work/runs/'
every = int(sys.argv[sys.argv.index('--every') + 1]) if '--every' in sys.argv else 10
names = [x for x in sys.argv[1:] if not x.startswith('--') and not x.isdigit()]


def load(name):
    m = json.load(open(R + name + '/samples.json'))
    out = {}
    for s in m['samples']:
        out.setdefault(s['frame'], s)       # first sample of each frame number (before any post-race reset)
    return out


a, b = (load(n) for n in names[:2])
common = sorted(set(a) & set(b))
print('common frames', common[0], '..', common[-1])
first = None
for f in common:
    x, y = a[f], b[f]
    d = math.dist(x['pos'], y['pos'])
    dt = x['t29E588'] - y['t29E588']
    if (d > 1e-4 or abs(dt) > 1e-5) and first is None:
        first = f
        print('first difference at frame', f, 'dist', round(d, 4), 'dt29E588', round(dt, 5))
    if f % every == 0 or f in (first,) or 180 <= f <= 192:
        print(f, 'cd', x['countdown'], y['countdown'], 'rf', x['raceFrames'], y['raceFrames'], 'pos', x['pos'], y['pos'],
              'd', round(d, 4), 'hud', round(x['hud'], 3), round(y['hud'], 3), 't29', round(x['t29E588'], 4), round(y['t29E588'], 4))
