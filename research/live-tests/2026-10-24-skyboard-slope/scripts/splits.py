"""Split times of the player along AI 0's lap line, for several runs.
python splits.py RUN [RUN...]   (run dirs under work/runs; times in s from GO, 60 vblanks/s)
"""
import json, math, sys
R = 'D:/sandboxes/racsm60fps/work/runs/'
P = json.load(open(R + 'banc-skyrace-wp/ai0-lap.json'))
N, K = len(P), 12


def track(run):
    m = json.load(open(R + run + '/samples.json'))
    s = m['samples']
    go = next(x['v'] for x in s if x['raceFrames'] > 0)
    s = [x for x in s if x['v'] >= go]
    cum, last, out, hud = None, None, [], {}
    for x in s:
        p = x['pos']
        if last is not None and math.dist(p, last) > 10:      # respawn: search the full lap again
            cum = None
        last = p
        if cum is None:
            base = 0 if not out else out[-1][1]
            j = min(range(N), key=lambda j: (P[j][0] - p[0]) ** 2 + (P[j][2] - p[2]) ** 2)
            cum = (base // N) * N + j if out else j
            if out and cum < out[-1][1] - N // 2:
                cum += N
        else:
            cum = min(range(cum - 3, cum + 30), key=lambda j: (P[j % N][0] - p[0]) ** 2 + (P[j % N][2] - p[2]) ** 2)
        k = cum * K // N
        hud.setdefault(k, []).append(x['hud'])
        if not out or k > out[-1][0]:
            out.append((k, cum, (x['v'] - go) / 60))
    return out, hud, m['config']


runs = sys.argv[1:]
res = {r: track(r) for r in runs}
print('seg', *[f'{res[r][2][:22]:>24}' for r in runs])
for k in range(K, 4 * K + 2):
    row = []
    for r in runs:
        d = dict((kk, t) for kk, _, t in res[r][0])
        if k in d and k - 1 in d:
            h = res[r][1].get(k - 1, [0])
            row.append(f'{d[k] - d[k - 1]:7.2f}s hud{sum(h) / len(h):5.1f} @{d[k]:6.1f}')
        else:
            row.append(' ' * 24)
    print(f'{k:3d}', *row)
