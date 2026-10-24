"""First race vblank (from GO) where two runs' player positions differ by more than 0.05 u.
python diverge.py RUN_A RUN_B"""
import json, math, sys

R = 'D:/sandboxes/racsm60fps/work/runs/'


def load(name):
    m = json.load(open(R + name + '/samples.json'))
    go = next(e['v'] for e in m['events'] if e.get('go'))
    return {s['v'] - go: s for s in m['samples']}, go


a, ga = load(sys.argv[1])
b, gb = load(sys.argv[2])
print('go', ga, gb)
common = sorted(set(a) & set(b))
print('common samples', len(common), 'from', common[0], 'to', common[-1])
for k in common:
    if k < 0:
        continue
    d = math.dist(a[k]['pos'], b[k]['pos'])
    if d > 0.05:
        print('diverge at race vblank', k, 'dist', round(d, 3), a[k]['pos'], b[k]['pos'],
              'raceFrames', a[k].get('raceFrames'), b[k].get('raceFrames'))
        break
else:
    print('no divergence')
