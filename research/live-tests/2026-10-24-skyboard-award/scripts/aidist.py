"""Distance from the player to each group entity (AI racers) over a time window.
python aidist.py RUN T0 T1 [STEP]   (seconds from GO)
"""
import json, math, sys
R = 'D:/sandboxes/racsm60fps/work/runs/'
run, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
step = float(sys.argv[4]) if len(sys.argv) > 4 else 0.25
m = json.load(open(R + run + '/samples.json'))
s = m['samples']
go = next(x['v'] for x in s if x['raceFrames'] > 0)
nxt = t0
for x in s:
    t = (x['v'] - go) / 60
    if t0 <= t <= t1 and t >= nxt and 'ents' in x:
        nxt = t + step
        d = [round(math.dist(x['pos'], e), 1) for e in x['ents'][:3]]
        print(f"{t:6.2f} hud {x['hud']:5.2f} d_ai {d}")
