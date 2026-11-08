"""Ground speed surfaces G+0x158 over a run (rec.py --watch <G+0x158>, LEVEL_22 G = RAM 0x940CC98).
python surfaces.py RUN [--addr 0x940cdf0]   (run dir under work/runs)
G+0x158 is the ground probe's surface class (0x4AAF4..: type 5 -> 1 accelerate, 3 -> 2 brake, else 0),
written every substep; the watch breaks only on a change. Prints every change after GO with the
writer PC and position, and the time spent in each class (60 vblanks/s).
"""
import argparse, collections, json, os

R = os.environ.get('RACSM_ROOT', 'D:/sandboxes/racsm60fps') + '/work/runs/'
ap = argparse.ArgumentParser()
ap.add_argument('run')
ap.add_argument('--addr', default='0x940cdf0')
a = ap.parse_args()
m = json.load(open(R + a.run + '/samples.json'))
s, ev = m['samples'], m['events']
pos = {x['v']: x for x in s}
go = next((e['v'] for e in ev if e.get('go')), s[0]['v'])
end = s[-1]['v']
ch = [e for e in ev if e.get('watch') == a.addr]
print(f'{a.run} ({m["config"]}): GO v{go}, last v{end}, {len(ch)} changes of the word at {a.addr}')
cls, since, spent = 0, go, collections.Counter()
for e in ch:
    old, new = e['old'] & 0xFF, e['new'] & 0xFF
    v = e['v'] if e['v'] is not None else go
    x = pos.get(v, {})
    print(f'  v{v:6d} ({(v - go) / 60:7.2f} s) pc {e["pc"]:>8} {old} -> {new}  pos {x.get("pos")}')
    if v >= go:
        spent[cls] += v - max(since, go)
        since = v
    cls = new
spent[cls] += end - max(since, go)
print('vblanks after GO per class:', dict(spent))
