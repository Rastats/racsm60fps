"""Waypoints from one AI trajectory of samples.json.

python mkwp.py samples.json entity_index out.json [--spacing 3] [--lap]
--lap keeps one closed lap: from the AI's position at GO (first raceFrames > 0) to its next
pass within --close u of that point, at least --min-frames race frames later.
"""
import argparse, json, math
ap = argparse.ArgumentParser()
ap.add_argument('samples')
ap.add_argument('entity', type=int)
ap.add_argument('out')
ap.add_argument('--spacing', type=float, default=3.0)
ap.add_argument('--lap', action='store_true')
ap.add_argument('--close', type=float, default=6.0)
ap.add_argument('--min-frames', type=int, default=1000)
a = ap.parse_args()
o = json.load(open(a.samples))
rows = [(s['raceFrames'], s['ents'][a.entity]) for s in o['samples'] if 'ents' in s]
if a.lap:
    k0 = next(k for k, (rf, _) in enumerate(rows) if rf > 0)
    rf0, p0 = rows[k0]
    near = [k for k in range(k0, len(rows)) if rows[k][0] - rf0 > a.min_frames
            and math.hypot(rows[k][1][0] - p0[0], rows[k][1][2] - p0[2]) < a.close]
    if not near:
        raise SystemExit('no closing pass found')
    # first pass of the closing run, then its nearest sample
    k1 = near[0]
    while k1 + 1 < len(rows) and math.dist(rows[k1 + 1][1], p0) < math.dist(rows[k1][1], p0):
        k1 += 1
    print('lap race frames', rf0, '->', rows[k1][0], '=', rows[k1][0] - rf0)
    tr = [p for _, p in rows[k0:k1]]
else:
    tr = [p for _, p in rows]
out = [tr[0]]
for p in tr[1:]:
    if math.hypot(p[0] - out[-1][0], p[2] - out[-1][2]) >= a.spacing:
        out.append(p)
json.dump(out, open(a.out, 'w'))
print(len(tr), '->', len(out), 'waypoints', 'lap' if a.lap else '')
