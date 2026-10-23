"""Respawn events of rec.py runs mapped to race frames and lap: resplap.py RUN FPS [RUN FPS ...]"""
import json, sys
from pathlib import Path
R = Path('D:/sandboxes/racsm60fps/work/runs')
args = sys.argv[1:]
for run, fps in zip(args[::2], args[1::2]):
    d = json.loads((R / run / 'samples.json').read_text())
    s, ev = d['samples'], d.get('events', [])
    rf = {e['v']: e['raceFrames'] for e in s}
    vs = sorted(rf)
    out = []
    for e in ev:
        if 'respawn' in e:
            v = max(x for x in vs if x <= e['v'])
            out.append((e['v'], rf[v], round(rf[v] / int(fps), 1)))
    print(run, out)
