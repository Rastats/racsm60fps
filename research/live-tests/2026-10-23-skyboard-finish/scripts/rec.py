"""Record a LEVEL_22 race: player, group entities, race words per frame; shots; optional autopilot.

python rec.py --state banc-skyboard-arrive --config A0 --seconds 60 --shot-every 300 --out DIR
  [--path waypoints.json [--lap]] [--boost] [--group 0x108CA8] [--stuck-stop] [--finish-after 15]

Times and input durations are in vblanks (1 per frame in C1, 2 in A0), so a script means the
same thing in both configs. samples.json is written even if the run stops on an error.
"""
import argparse, ctypes, json, math, struct, sys, threading, time
from pathlib import Path
# per-monitor DPI awareness: without it PrintWindow returns the 125 %-scaled window cut to its logical size
ctypes.windll.shcore.SetProcessDpiAwareness(2)
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
ap.add_argument('--shot-every', type=int, default=0, help='vblanks between shots')
ap.add_argument('--group', type=lambda s: int(s, 16), action='append', default=[])
ap.add_argument('--path', type=Path, nargs='+', default=[], help='one or more AI lines; the autopilot follows '
                'the one nearest the player in height (upper and lower routes overlap on the ground)')
ap.add_argument('--lap', action='store_true', help='each path is one closed lap: index it modulo its length')
ap.add_argument('--level-dy', type=float, default=4.0, help='height gap (u) to the followed line that means '
                'another level: the autopilot then takes the line nearest in height')
ap.add_argument('--look', type=float, default=12.0, help='autopilot look-ahead distance (u)')
ap.add_argument('--gain', type=float, default=1.0 / 25, help='stick per degree of heading error')
ap.add_argument('--boost', action='store_true')
ap.add_argument('--jump-rise', type=float, default=0.4, help='AI line rise (u) that triggers a jump (0: off)')
ap.add_argument('--jump-xz', default='', help='ground points "x,z;x,z" where the board jumps')
ap.add_argument('--jump-r', type=float, default=4.0, help='radius (u) of a --jump-xz point')
ap.add_argument('--jump-ahead', type=float, default=8.0, help='path distance (u) scanned for a rise')
ap.add_argument('--jump-hold', type=int, default=60, help='vblanks per jump: cross held the first half')
ap.add_argument('--stuck-vb', type=int, default=600, help='window (vblanks) of the stuck check')
ap.add_argument('--stuck-dist', type=float, default=15.0, help='less displacement (u) than this over the window = stuck')
ap.add_argument('--stuck-stop', action='store_true', help='end the run at the first stuck check')
ap.add_argument('--finish-after', type=float, default=0, help='once raceFrames freezes 120 vblanks: keep '
                'shooting every 60 vblanks for this many seconds, then stop (0: no finish detection)')
ap.add_argument('--gap-every', type=float, default=1.0, help='wall seconds between shots while no frame arrives (0: off)')
ap.add_argument('--fin-every', type=int, default=30, help='vblanks between shots after the finish')
ap.add_argument('--save-at', type=int, default=0, help='race vblank (from GO) at which to save --save-name')
ap.add_argument('--save-name', default='')
ap.add_argument('--stop-on', default='', help='python expr on s (sample) that ends the run')
ap.add_argument('--watch', type=lambda s: int(s, 16), action='append', default=[],
                help='absolute address: log PC, ra and new value of every store that changes it (events)')
ap.add_argument('--out', type=Path, required=True)
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
pid = int((DEFAULT_INSTANCE / 'bench.pid').read_text())
paths = [json.loads(p.read_text()) for p in a.path]
jump_xz = [tuple(float(c) for c in q.split(',')) for q in a.jump_xz.split(';') if q]
if a.state != '-':
    states.load(a.state)
    time.sleep(1.0)
samples, events = [], []
meta = {'config': a.config, 'args': {k: str(v) for k, v in vars(a).items()}}
try:
    with Debugger(DEFAULT_PORT).connect() as d:
        d.release_all()
        core, *fx = a.config.split('+')
        applied = wordfix.apply(d, core, set(fx))
        meta['applied'] = len(applied['writes'])
        base, prof = levels.profile(d)
        pos = base + prof['player'] + 0x30
        for _ in range(20):        # right after a state load the entity manager can still be unset
            try:
                grp = {g['callback']: g for g in entities.groups(d, base)}
                if all(cb in grp for cb in a.group):   # groups register a little after the manager
                    break
                time.sleep(0.5)
            except Exception:
                time.sleep(0.5)
        else:
            raise SystemExit('entity manager not readable 10 s after the state load')
        ents = [(cb, k, grp[cb]['entities'] + k * 0x80) for cb in a.group for k in range(grp[cb]['capacity'])]
        meta['ents'] = [[hex(cb), k] for cb, k, _ in ents]
        t0, cur, prev = [], {'s': None, 'b': None, 'j': None}, []
        st = {'jump_until': -1, 'go': None, 'rf_last': None, 'rf_v': 0, 'finish_v': None,
              'stuck_next': None, 'saved': False, 'line': 0}
        L = len(paths)
        idx = [None] * L

        def wp(li, j):
            w = paths[li]
            return w[j % len(w)] if a.lap else w[max(0, min(j, len(w) - 1))]

        def seg(li, j):
            p, q = wp(li, j), wp(li, j + 1)
            return math.hypot(q[0] - p[0], q[2] - p[2])

        def nearest(li, p, lo, hi):
            # height counts double, so an upper and a lower route over the same ground stay apart
            return min(range(lo, hi), key=lambda j: (wp(li, j)[0] - p[0]) ** 2 + (wp(li, j)[2] - p[2]) ** 2
                       + 4 * (wp(li, j)[1] - p[1]) ** 2)

        def score(li, p):
            q = wp(li, idx[li])
            return math.hypot(q[0] - p[0], q[2] - p[2]) + 3 * abs(q[1] - p[1])

        def steer(p, s, v):
            if not paths or not prev:
                return (0.0, 0.0)
            dx, dz = p[0] - prev[0][0], p[2] - prev[0][2]
            step = math.hypot(dx, dz)
            if idx[0] is None or step > 10:
                # first frame, or a respawn: search every line in full
                if idx and idx[0] is not None:        # no --path: nothing to index
                    events.append({'v': v, 'respawn': [round(c, 2) for c in p], 'from': [round(c, 2) for c in prev[0]]})
                for li in range(L):
                    n = len(paths[li])
                    base_i = (idx[li] // n) * n if (a.lap and idx[li] is not None) else 0
                    idx[li] = base_i + nearest(li, p, 0, n)
                return (0.0, 0.0)
            if step < 1e-3:
                return (0.0, 0.0)
            for li in range(L):
                i = idx[li]
                hi = i + 60 if a.lap else min(i + 60, len(paths[li]))
                idx[li] = nearest(li, p, i - 5 if a.lap else max(0, i - 5), hi)
            # change line only when the followed one is on another level than the player
            dy = [abs(wp(li, idx[li])[1] - p[1]) for li in range(L)]
            sc = [score(li, p) for li in range(L)]
            b = min(range(L), key=lambda li: (dy[li], sc[li]))
            if b != st['line'] and dy[st['line']] > a.level_dy and dy[b] < dy[st['line']] - 2:
                events.append({'v': v, 'line': b, 'from': st['line'], 'pos': [round(c, 2) for c in p],
                               'scores': [round(x, 1) for x in sc]})
                st['line'] = b
            li = st['line']
            best = idx[li]
            j, acc = best, 0.0
            while (a.lap or j + 1 < len(paths[li])) and acc < a.look:
                acc += seg(li, j)
                j += 1
            tx, tz = wp(li, j)[0] - p[0], wp(li, j)[2] - p[2]
            err = math.degrees(math.atan2(tx, tz) - math.atan2(dx, dz))
            err = (err + 180) % 360 - 180
            s['line'] = li
            s['wp'] = best
            s['err'] = round(err, 1)
            # jump at listed ground points (--jump-xz x,z;...), within --jump-r u
            if v >= st['jump_until'] and any(math.hypot(p[0] - x, p[2] - z) < a.jump_r for x, z in jump_xz):
                st['jump_until'] = v + a.jump_hold
                s['jump'] = 1
            # jump where the AI line climbs (a hop over a step): rise within --jump-ahead u of path
            k, acc = best, 0.0
            while a.jump_rise > 0 and (a.lap or k + 1 < len(paths[li])) and acc < a.jump_ahead:
                acc += seg(li, k)
                k += 1
                if wp(li, k)[1] - wp(li, best)[1] > a.jump_rise and v >= st['jump_until']:
                    st['jump_until'] = v + a.jump_hold
                    s['jump'] = 1
                    break
            # heading grows with stick left (-1): +102 deg per s in the 2026-10-23 report
            return (max(-1.0, min(1.0, -err * a.gain)), 0.0)

        def shot(name, s):
            f = a.out / name
            wincap.capture(pid, f)
            s['shot'] = f.name

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
            racing = s['raceFrames'] > 0
            if racing and st['go'] is None:
                st['go'] = v
                st['stuck_next'] = v + a.stuck_vb
                events.append({'v': v, 'go': True})
            stk = steer(p, s, v) if racing else (0.0, 0.0)
            prev[:] = [p]
            if idx and idx[0] is not None:        # no --path: nothing to index
                s['lapIdx'] = idx[st['line']]
            b = bool(a.boost and racing)
            j = v < st['jump_until'] - a.jump_hold // 2      # held for the first half, released for the second
            if stk != cur['s']:
                d.stick(*stk); cur['s'] = stk
            if b != cur['b']:
                d.buttons(square=b); cur['b'] = b
            if j != cur['j']:
                d.buttons(cross=j); cur['j'] = j
            if a.shot_every and v // a.shot_every != (samples[-1]['v'] // a.shot_every if samples else -1):
                shot(f'v{v:05d}.png', s)
            samples.append(s)
            # save a mid-race state
            if a.save_at and a.save_name and not st['saved'] and st['go'] is not None and v - st['go'] >= a.save_at:
                st['saved'] = True
                events.append({'v': v, 'save': a.save_name, 'pos': s['pos'], 'lapIdx': idx[st['line']] if idx else None, 'line': st['line']})
                return True
            # finish: after GO, raceFrames frozen for 120 vblanks or reset below its last value
            # (it falls to 0 when the race ends, OBSERVED 2026-10-23 banc-skyrace-a0-boost)
            if st['go'] is not None and a.finish_after:
                rf = s['raceFrames']
                if st['finish_v'] is None:
                    reset = st['rf_last'] is not None and rf < st['rf_last']
                    if reset or (rf == st['rf_last'] and v - st['rf_v'] >= 120):
                        st['finish_v'] = v
                        events.append({'v': v, 'finish': 'reset' if reset else 'frozen', 'raceFrames': rf,
                                       'lastRaceFrames': st['rf_last'], 'lastChangeV': st['rf_v'], 't': t})
                    elif rf != st['rf_last']:
                        st['rf_last'], st['rf_v'] = rf, v
                if st['finish_v'] is not None:
                    if (v - st['finish_v']) // a.fin_every != (samples[-2]['v'] - st['finish_v']) // a.fin_every:
                        shot(f'fin-v{v:05d}.png', s)
                    if v - st['finish_v'] >= a.finish_after * 60:
                        return True
            # stuck check: displacement over the last --stuck-vb vblanks
            if st['stuck_next'] is not None and v >= st['stuck_next'] and st['finish_v'] is None:
                st['stuck_next'] = v + a.stuck_vb // 4
                old = next((x for x in reversed(samples) if x['v'] <= v - a.stuck_vb), None)
                if old and math.dist(old['pos'], p) < a.stuck_dist:
                    events.append({'v': v, 'stuck': s['pos'], 'lapIdx': idx[st['line']] if idx else None, 'line': st['line']})
                    shot(f'stuck-v{v:05d}.png', s)
                    if a.stuck_stop:
                        return True
            if a.stop_on and eval(a.stop_on, {'math': math}, {'s': s, 'samples': samples}):
                shot(f'stop-v{v:05d}.png', s)
                return True

        # Screens outside the race loop (the win sequence, loading) do not advance the frame counter, so
        # no frame callback shoots them (OBSERVED 2026-10-23: no frame for ~1000 vblanks after a win).
        # A wall-clock thread captures once per second while no frame has arrived for 0.5 s.
        last_cb = [time.monotonic()]
        done = threading.Event()

        def gap_shooter():
            k = 0
            while not done.wait(a.gap_every):
                if time.monotonic() - last_cb[0] > 0.5:
                    f = a.out / f'gap-{k:03d}-after-v{samples[-1]["v"] if samples else 0:05d}.png'
                    try:
                        wincap.capture(pid, f)
                        events.append({'gapShot': f.name, 'wall': round(time.monotonic() - t_wall0, 1)})
                    except Exception as e:  # noqa: BLE001 - a missed shot must not end the run
                        events.append({'gapShotError': str(e)})
                    k += 1
        t_wall0 = time.monotonic()
        if a.gap_every:
            threading.Thread(target=gap_shooter, daemon=True).start()
        frame_cb = on_frame

        def on_frame_timed(t, value):
            last_cb[0] = time.monotonic()
            return frame_cb(t, value)

        loop = BreakLoop(d, base)
        loop.every_frame(on_frame_timed)
        for wa in a.watch:
            def on_store(t, old, new, wa=wa):
                ra = d.call('cpu.getReg', category=0, register=31)['uintValue']
                events.append({'v': samples[-1]['v'] if samples else None, 'watch': hex(wa), 'pc': hex(int(d.cpu()['pc']) - base),
                               'ra': hex(ra - base), 'old': old, 'new': new})
            loop.watch(wa, on_store)
        loop.at_end(lambda: d.release_all())
        try:
            loop.run(a.seconds, wall_limit=a.seconds * 3 + 120)
        finally:
            done.set()
        if st['saved']:
            # the run ends at --save-at; the state is taken a few frames later, inputs released
            states.save(a.save_name)
finally:
    meta.update({'events': events, 'samples': samples})
    (a.out / 'samples.json').write_text(json.dumps(meta) + '\n')
for s in samples[:: max(1, len(samples) // 40)]:
    print(s['v'], s['frame'], s['pos'], s['countdown'], s['raceFrames'], round(s['hud'], 2), s.get('line', ''), s.get('lapIdx', ''), s.get('err', ''), s.get('shot', ''))
print('events', json.dumps(events))
if samples:
    print('frames', len(samples), 'last', samples[-1]['v'], samples[-1]['pos'], samples[-1]['raceFrames'])
