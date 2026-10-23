"""Record a LEVEL_22 race: player, group entities, race words per frame; shots; optional autopilot.

python rec.py --state banc-skyboard-arrive --config A0 --seconds 60 --shot-every 300 --out DIR
  [--path waypoints.json] [--boost] [--group 0x108CA8]
"""
import argparse, json, math, struct, sys, time
from pathlib import Path
BENCH = Path('D:/sandboxes/racsm60fps/wt-banc/tools/bench')
sys.path.insert(0, str(BENCH))
from ppsspp_bench import Debugger, DEFAULT_PORT, DEFAULT_INSTANCE  # noqa
from breakloop import BreakLoop  # noqa
import states, wordfix, levels, wincap, entities  # noqa

VB = 3_703_700
WORDS = {'countdown': (0x22DDCC, 'i'), 'raceFrames': (0x240658, 'i'), 'hud': (0x22DC0C, 'f'),
         'clock': (0x227D04, 'f'), 't29E588': (0x29E588, 'f')}
ap = argparse.ArgumentParser()
ap.add_argument('--state', required=True)
ap.add_argument('--config', default='A0')
ap.add_argument('--seconds', type=float, default=60)
ap.add_argument('--shot-every', type=int, default=0)
ap.add_argument('--group', type=lambda s: int(s, 16), action='append', default=[])
ap.add_argument('--path', type=Path)
ap.add_argument('--look', type=float, default=12.0, help='autopilot look-ahead distance (u)')
ap.add_argument('--gain', type=float, default=1.0 / 25, help='stick per degree of heading error')
ap.add_argument('--boost', action='store_true')
ap.add_argument('--jump-rise', type=float, default=0.4, help='AI line rise (u) that triggers a jump')
ap.add_argument('--jump-ahead', type=float, default=8.0, help='path distance (u) scanned for a rise')
ap.add_argument('--jump-hold', type=int, default=30, help='frames per jump: cross held the first half')
ap.add_argument('--stop-on', default='', help='python expr on s (sample) that ends the run')
ap.add_argument('--out', type=Path, required=True)
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
pid = int((DEFAULT_INSTANCE / 'bench.pid').read_text())
path = json.loads(a.path.read_text()) if a.path else None
if a.state != '-':
    states.load(a.state)
    time.sleep(1.0)
with Debugger(DEFAULT_PORT).connect() as d:
    d.release_all()
    core, *fx = a.config.split('+')
    applied = wordfix.apply(d, core, set(fx))
    base, prof = levels.profile(d)
    pos = base + prof['player'] + 0x30
    grp = {g['callback']: g for g in entities.groups(d, base)}
    ents = [(cb, k, grp[cb]['entities'] + k * 0x80) for cb in a.group for k in range(grp[cb]['capacity'])]
    samples, t0, cur, prev, idx, jump = [], [], {'s': None, 'b': None, 'j': None}, [], [0], [0]

    def steer(p, s):
        if not path or not prev:
            return (0.0, 0.0)
        dx, dz = p[0] - prev[0][0], p[2] - prev[0][2]
        if math.hypot(dx, dz) < 1e-3:
            return (0.0, 0.0)
        # advance the waypoint index to the nearest point ahead, then look ahead
        i = idx[0]
        best = min(range(i, min(i + 60, len(path))), key=lambda j: (path[j][0] - p[0]) ** 2 + (path[j][2] - p[2]) ** 2)
        idx[0] = best
        j, acc = best, 0.0
        while j + 1 < len(path) and acc < a.look:
            acc += math.hypot(path[j + 1][0] - path[j][0], path[j + 1][2] - path[j][2])
            j += 1
        tx, tz = path[j][0] - p[0], path[j][2] - p[2]
        err = math.degrees(math.atan2(tx, tz) - math.atan2(dx, dz))
        err = (err + 180) % 360 - 180
        s['wp'] = best
        s['err'] = round(err, 1)
        # jump where the AI line climbs (a hop over a step): rise within --jump-ahead u of path
        k, acc = best, 0.0
        while k + 1 < len(path) and acc < a.jump_ahead:
            acc += math.hypot(path[k + 1][0] - path[k][0], path[k + 1][2] - path[k][2])
            k += 1
            if path[k][1] - path[best][1] > a.jump_rise and jump[0] <= 0:
                jump[0] = a.jump_hold
                s['jump'] = 1
                break
        # heading grows with stick left (-1): +102 deg per s in the 2026-10-23 report
        return (max(-1.0, min(1.0, -err * a.gain)), 0.0)

    def on_frame(t, value):
        if value is None:
            return
        if not t0:
            t0.append(t)
        v = round((t - t0[0]) / VB)
        p = list(struct.unpack('<3f', d.read(pos, 12)))
        s = {'t': t, 'v': v, 'frame': value, 'pos': [round(c, 3) for c in p]}
        for name, (rva, kind) in WORDS.items():
            s[name] = d.f32(base + rva) if kind == 'f' else struct.unpack('<i', d.read(base + rva, 4))[0]
        if ents and len(samples) % 2 == 0:
            s['ents'] = [[round(c, 2) for c in struct.unpack('<3f', d.read(e + 0x30, 12))] for _, _, e in ents]
        racing = s['countdown'] == 0 or s['raceFrames'] > 0
        stk = steer(p, s) if racing else (0.0, 0.0)
        prev[:] = [p]
        b = bool(a.boost and racing and s['raceFrames'] > 0)
        j = jump[0] > a.jump_hold // 2      # held for the first half, released for the second
        jump[0] -= 1
        if stk != cur['s']:
            d.stick(*stk); cur['s'] = stk
        if b != cur['b']:
            d.buttons(square=b); cur['b'] = b
        if j != cur['j']:
            d.buttons(cross=j); cur['j'] = j
        if a.shot_every and v // a.shot_every != (samples[-1]['v'] // a.shot_every if samples else -1):
            f = a.out / f'v{v:05d}.png'
            wincap.capture(pid, f)
            s['shot'] = f.name
        samples.append(s)
        if a.stop_on and eval(a.stop_on, {}, {'s': s, 'samples': samples}):
            f = a.out / f'stop-v{v:05d}.png'
            wincap.capture(pid, f)
            s['shot'] = f.name
            return True

    loop = BreakLoop(d, base)
    loop.every_frame(on_frame)
    loop.at_end(lambda: d.release_all())
    loop.run(a.seconds, wall_limit=a.seconds * 60)
(a.out / 'samples.json').write_text(json.dumps({'config': a.config, 'applied': len(applied['writes']),
                                               'ents': [[hex(cb), k] for cb, k, _ in ents], 'samples': samples}) + '\n')
for s in samples[:: max(1, len(samples) // 40)]:
    print(s['v'], s['frame'], s['pos'], s['countdown'], s['raceFrames'], round(s['hud'], 2), s.get('wp', ''), s.get('err', ''), s.get('shot', ''))
print('frames', len(samples), 'last', samples[-1]['v'], samples[-1]['pos'], samples[-1]['raceFrames'])
