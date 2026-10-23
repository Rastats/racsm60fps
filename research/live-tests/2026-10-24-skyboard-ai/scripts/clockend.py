"""clock / raceFrames / ticks around the finish of a rec.py run: clockend.py RUN [RUN...]"""
import json, sys
from pathlib import Path
R = Path('D:/sandboxes/racsm60fps/work/runs')
for run in sys.argv[1:]:
    s = json.loads((R / run / 'samples.json').read_text())['samples']
    r = [e for e in s if e['raceFrames'] > 0]
    a, b = r[0], max(r, key=lambda e: e['raceFrames'])
    last = next(e for e in r if e['raceFrames'] == b['raceFrames'])
    dt = (last['t'] - a['t']) / 222e6
    print(run, 'first', a['raceFrames'], round(a['clock'], 3), 'end', last['raceFrames'], round(last['clock'], 3),
          'dClock', round(last['clock'] - a['clock'], 2), 'dFrames', last['raceFrames'] - a['raceFrames'], 'dEmuS', round(dt, 2))
