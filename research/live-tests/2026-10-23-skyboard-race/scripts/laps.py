"""Player passes near the start line in a rec.py samples.json, with race frame and vblank.
python laps.py samples.json [x z r]"""
import json, math, sys
o = json.load(open(sys.argv[1]))
x0, z0, r = (float(v) for v in sys.argv[2:5]) if len(sys.argv) > 4 else (-112.0, 66.0, 25.0)
s = o['samples']
print('keys', sorted(s[0].keys()), 'n', len(s))
near, last = [], None
for k, e in enumerate(s):
    p = e.get('pos')
    if not p:
        continue
    d = math.hypot(p[0] - x0, p[2] - z0)
    if d < r and (last is None or e['raceFrames'] - last > 600):
        near.append((e.get('v'), e['raceFrames'], [round(c, 1) for c in p], round(d, 1)))
        last = e['raceFrames']
for n in near:
    print(n)
ev = [x for x in o['events'] if 'line' not in x]
print('events', ev[:20])
