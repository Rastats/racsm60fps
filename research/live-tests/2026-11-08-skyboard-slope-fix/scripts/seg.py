"""Player trace through one stretch of the lap: time, pos, hud, line, err, events nearby.
python seg.py RUN T0 T1 [STEP]   (seconds from GO)
"""
import json, sys
R = 'D:/sandboxes/racsm60fps/work/runs/'
run, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
step = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
m = json.load(open(R + run + '/samples.json'))
s = m['samples']
go = next(x['v'] for x in s if x['raceFrames'] > 0)
nxt = t0
for x in s:
    t = (x['v'] - go) / 60
    if t0 <= t <= t1 and t >= nxt:
        nxt = t + step
        print(f"{t:6.2f} pos {x['pos'][0]:8.2f} {x['pos'][1]:6.2f} {x['pos'][2]:8.2f} hud {x['hud']:5.2f} line {x.get('line','')} wp {x.get('wp','')} err {x.get('err','')}")
for e in m['events']:
    if 'v' in e and e['v'] is not None and t0 <= (e['v'] - go) / 60 <= t1:
        print('event', round((e['v'] - go) / 60, 2), {k: v for k, v in e.items() if k != 'v'})
