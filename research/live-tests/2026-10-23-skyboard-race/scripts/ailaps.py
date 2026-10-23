"""Start-line passes (race frames) of the player and AI entities 0-2 in a rec.py samples.json.
A pass = first sample within r u (xz) of the entity's own GO position, > min frames after the previous.
python ailaps.py samples.json [fps]"""
import json, math, sys
o = json.load(open(sys.argv[1]))
fps = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
s = [e for e in o['samples'] if e.get('pos')]
k0 = next(k for k, e in enumerate(s) if e['raceFrames'] > 0)


def passes(get, r=8.0, gap=900):
    p0 = next((get(e) for e in s[k0:] if get(e)), None)
    if p0 is None:
        return []
    out, last = [], s[k0]['raceFrames']
    for e in s[k0:]:
        p = get(e)
        if p and math.hypot(p[0] - p0[0], p[2] - p0[2]) < r and e['raceFrames'] - last > gap:
            out.append(e['raceFrames'])
            last = e['raceFrames']
    return out


who = [('player', lambda e: e['pos'])] + [(f'ai{i}', lambda e, i=i: e['ents'][i] if 'ents' in e else None)
                                          for i in range(3)]
end = s[-1]['raceFrames']
print('race end raceFrames', end, '=', round(end / fps, 1), 's')
for name, get in who:
    ps = passes(get)
    laps = [b - a for a, b in zip([s[k0]['raceFrames']] + ps, ps)]
    print(name, 'passes', ps, 'laps s', [round(x / fps, 1) for x in laps])
