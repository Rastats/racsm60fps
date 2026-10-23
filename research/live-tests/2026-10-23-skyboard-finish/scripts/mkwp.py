"""Waypoints from one AI trajectory of samples.json: mkwp.py samples.json entity_index out.json [spacing]."""
import json, math, sys
o = json.load(open(sys.argv[1]))
i, spacing = int(sys.argv[2]), float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
tr = [s['ents'][i] for s in o['samples'] if 'ents' in s]
out = [tr[0]]
for p in tr[1:]:
    if math.hypot(p[0] - out[-1][0], p[2] - out[-1][2]) >= spacing:
        out.append(p)
json.dump(out, open(sys.argv[3], 'w'))
print(len(tr), '->', len(out), 'waypoints')
