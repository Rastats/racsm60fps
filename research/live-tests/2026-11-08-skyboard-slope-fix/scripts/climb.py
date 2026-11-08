"""Passes of the player through the climb box (105-115, y, -113..-108): time from GO, HUD, pos.
python climb.py RUN [RUN...] [--box x0,x1,z0,z1] [--pad S]   (run dirs under work/runs; 60 vblanks/s)
"""
import argparse, json, math
R = 'D:/sandboxes/racsm60fps/work/runs/'
ap = argparse.ArgumentParser()
ap.add_argument('runs', nargs='+')
ap.add_argument('--box', default='100,120,-118,-103')
ap.add_argument('--pad', type=float, default=0.0, help='seconds printed before and after each pass')
ap.add_argument('--every', type=int, default=1, help='print every Nth sample')
a = ap.parse_args()
x0, x1, z0, z1 = (float(c) for c in a.box.split(','))
for run in a.runs:
    m = json.load(open(R + run + '/samples.json'))
    s = m['samples']
    go = next(x['v'] for x in s if x['raceFrames'] > 0)
    inside = [i for i, x in enumerate(s) if x['v'] >= go and x0 <= x['pos'][0] <= x1 and z0 <= x['pos'][2] <= z1]
    passes, cur = [], []
    for i in inside:
        if cur and i - cur[-1] > 20:
            passes.append(cur); cur = []
        cur.append(i)
    if cur:
        passes.append(cur)
    print(f'== {run} ({m["config"]}), GO v{go}, {len(passes)} passes')
    for p in passes:
        i0, i1 = p[0], p[-1]
        t0, t1 = (s[i0]['v'] - go) / 60, (s[i1]['v'] - go) / 60
        hud = [s[i]['hud'] for i in p]
        print(f'  pass {t0:7.2f}-{t1:7.2f}s dur {t1 - t0:5.2f} hud min {min(hud):5.2f} mean {sum(hud) / len(hud):5.2f}'
              f' in {s[i0]["pos"]} out {s[i1]["pos"]}')
        if a.pad >= 0 and a.every:
            for x in s:
                t = (x['v'] - go) / 60
                if t0 - a.pad <= t <= t1 + a.pad and (x['v'] - go) % (a.every * (1 if m['config'] != 'A0' else 2)) == 0:
                    print(f'    {t:7.2f} v{x["v"] - go:6d} pos {x["pos"][0]:8.2f} {x["pos"][1]:6.2f} {x["pos"][2]:8.2f} hud {x["hud"]:5.2f}')
