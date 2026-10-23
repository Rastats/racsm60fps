#!/usr/bin/env python3
"""Skyboard A/B/C on LEVEL_22 (Kalidon): speed, steering and race timers in emulated time.

Like move_probe.py, but every time is counted from GO, the first game frame
where the board moves, not from the first frame after loading. Loading a state
leaves a variable wall-clock settle during which emulation runs, and C1 counts
the pre-race countdown twice as fast as A0, so a script counted from the first
frame would hit a different point of the track in each config (OBSERVED
2026-10-23: the countdown starts at vblank 66 in one A0 run and 24 in a C1 run).

Per game frame (frame counter break, breakloop.py) the probe records the tick,
the board position (player + 0x30, LEVEL_22 player RVA from levels.py) and the
words below. RVAs are LEVEL_22 module offsets found on 2026-10-23 by RAM scans
(values tracking emulated time across paused dumps) and, for the HUD speed, by
matching the displayed number; their meaning is the observed behaviour only.

  hudSpeed     0x22DC0C  float, the number shown top right (10-15 when cruising)
  countdown    0x22DDCC  int, 135 -> 0 before GO, then 180 -> 0 after it
  raceFrames   0x240658  int, +1 per game frame from about GO
  clock227D04  0x227D04  float, +1/30 per game frame
  timer29E588  0x29E588  float, -1/15 per game frame in A0
  player574    0x29E0F4  float, player + 0x574, +1 per emulated second in A0

Scripts (vblanks after GO; vblank = 1001/60000 s; nothing is pressed before GO):
  straight   no input for 300 vblanks (5 s): the course's own line, speed curve
  turn       stick fully right (--side 1) or left (-1) from 60 to 120, neutral to 300
  button     --button held from 60 to 180, neutral to 300 (control mapping)

Metrics, per config, at equal emulated times after GO (positions interpolated
linearly between frame samples, so A0 at 30 Hz and C1 at 60 Hz compare at the
same instant): distance along the path, speed from positions, HUD speed,
heading of the velocity (degrees, atan2(dx, dz)), and the timer values.

Usage:
  python tools/bench/board_probe.py --state banc-skyboard-arrive --script straight \
      --configs A0 C1 --repeat 2 --out <root>/work/runs/banc-sky-straight-001
"""
import argparse
import itertools
import json
import math
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ppsspp_bench import Debugger, DEFAULT_PORT, BenchError  # noqa: E402
from breakloop import BreakLoop, CPU_HZ  # noqa: E402
import states  # noqa: E402
import wordfix  # noqa: E402
import levels  # noqa: E402

VBLANK_TICKS = 3_703_700
VBLANK_S = 1001 / 60000
POS = 0x30
LEVEL = 'LEVEL_22'
WORDS = {     # name: (LEVEL_22 RVA, 'f' float or 'i' int)
    'hudSpeed': (0x22DC0C, 'f'),
    'countdown': (0x22DDCC, 'i'),
    'raceFrames': (0x240658, 'i'),
    'clock227D04': (0x227D04, 'f'),
    'timer29E588': (0x29E588, 'f'),
    'player574': (0x29E0F4, 'f'),
}
SCRIPTS = ('straight', 'turn', 'button')
AFTER_GO = 300                # vblanks recorded after GO
PRE_GO_LIMIT = 20.0           # emulated seconds allowed before GO
MOVE_EPS = 1e-3               # horizontal step that counts as moving
TIMES_S = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 4.9)


def script(name, side=1, button='cross'):
    """[(start, end, input)] in vblanks after GO; input held on [start, end)."""
    return {
        'straight': [],
        'turn': [(60, 120, {'stick': (float(side), 0.0)})],
        'button': [(60, 180, {button: True})],
    }[name]


def wanted(spec, v):
    stick, held = (0.0, 0.0), set()
    for start, end, inp in spec:
        if start <= v < end:
            stick = inp.get('stick', stick)
            held |= {k for k in inp if k != 'stick'}
    return stick, frozenset(held)


def play(d, spec):
    base, prof = levels.profile(d)
    if prof['stem'] != LEVEL:
        raise BenchError(f'board_probe needs {LEVEL}, resident: {prof["stem"]}')
    pos_addr = base + prof['player'] + POS
    buttons = sorted({k for _, _, inp in spec for k in inp if k != 'stick'})
    samples, go, cur, prev, armed = [], [], {'stick': None, 'held': None}, [], [False]

    def on_frame(t, value):
        if value is None:
            return
        x, y, z = struct.unpack('<3f', d.read(pos_addr, 12))
        s = {'t': t, 'frame': value, 'pos': [x, y, z]}
        for name, (rva, kind) in WORDS.items():
            s[name] = d.f32(base + rva) if kind == 'f' else struct.unpack('<i', d.read(base + rva, 4))[0]
        # The first frames after a load can still move the player (scene reset), so GO
        # only counts once the pre-race countdown is running
        armed[0] = armed[0] or s['countdown'] > 0
        if armed[0] and not go and prev and math.hypot(x - prev[0][0], z - prev[0][2]) > MOVE_EPS:
            go.append(prev[0][3])          # GO = tick of the last still frame
        prev[:] = [(x, y, z, t)]
        samples.append(s)
        if go:
            v = round((t - go[0]) / VBLANK_TICKS)
            if v >= AFTER_GO + 2:
                return True
            stick, held = wanted(spec, v) if v < AFTER_GO else ((0.0, 0.0), frozenset())
            if stick != cur['stick']:
                d.stick(*stick)
                cur['stick'] = stick
            if held != cur['held'] and buttons:
                d.buttons(**{b: b in held for b in buttons})
                cur['held'] = held

    def release():
        d.release_all()

    loop = BreakLoop(d, base)
    loop.every_frame(on_frame)
    loop.at_end(release)
    # GO is unknown in advance: on_frame ends the run AFTER_GO vblanks past it.
    loop.run(PRE_GO_LIMIT + AFTER_GO * VBLANK_S)
    if not go or samples[-1]['t'] - go[0] < AFTER_GO * VBLANK_TICKS:
        raise BenchError(f'GO plus {AFTER_GO} vblanks not reached within {PRE_GO_LIMIT} emulated s')
    for s in samples:
        s['v'] = round((s['t'] - go[0]) / VBLANK_TICKS)
    return go[0], samples


def interp(samples, t_rel, key):
    """Linear interpolation of a position component or word at t_rel ticks after GO."""
    for a, b in zip(samples, samples[1:]):
        if a['tr'] <= t_rel <= b['tr']:
            f = (t_rel - a['tr']) / (b['tr'] - a['tr'])
            return a[key] + f * (b[key] - a[key])
    return None


def metrics(go, samples):
    for s in samples:
        s['tr'] = s['t'] - go
        s['x'], s['y'], s['z'] = s['pos']
    post = [s for s in samples if s['tr'] >= 0]
    path = 0.0
    for a, b in zip(post, post[1:]):
        b['path'] = path = path + math.hypot(b['x'] - a['x'], b['z'] - a['z'])
    post[0]['path'] = 0.0
    out = {'frames': len(post), 'atS': {}}
    pre = [s for s in samples if s['tr'] <= 0]
    starts = [s for a, s in zip(pre, pre[1:]) if s['countdown'] > a['countdown'] + 50]
    if starts:
        out['countdownFromStartToGoS'] = round((go - starts[0]['t']) / CPU_HZ, 4)
        out['countdownSetTo'] = starts[0]['countdown']
    out['raceFramesAtGo'] = post[0]['raceFrames']
    dt_h = 4 * VBLANK_TICKS
    for ts in TIMES_S:
        tr = int(ts / VBLANK_S * VBLANK_TICKS)
        x0, z0 = interp(post, tr - dt_h, 'x'), interp(post, tr - dt_h, 'z')
        x1, z1 = interp(post, tr + dt_h, 'x'), interp(post, tr + dt_h, 'z')
        row = {'path': interp(post, tr, 'path'), 'x': interp(post, tr, 'x'), 'y': interp(post, tr, 'y'),
               'z': interp(post, tr, 'z')}
        if None not in (x0, z0, x1, z1):
            span = 2 * dt_h / CPU_HZ
            row['speedUps'] = math.hypot(x1 - x0, z1 - z0) / span
            row['headingDeg'] = math.degrees(math.atan2(x1 - x0, z1 - z0))
        for name, (_rva, kind) in WORDS.items():       # ints: last frame at or before the instant
            row[name] = interp(post, tr, name) if kind == 'f' else [s[name] for s in post if s['tr'] <= tr][-1]
        out['atS'][ts] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--state', required=True)
    ap.add_argument('--script', choices=SCRIPTS, required=True)
    ap.add_argument('--configs', nargs='+', required=True)
    ap.add_argument('--side', type=int, nargs='+', default=[1], help='turn: 1 = right, -1 = left')
    ap.add_argument('--button', default='cross', help='button script: the button held')
    ap.add_argument('--settle', type=float, default=1.0, help='wall seconds after loading the state')
    ap.add_argument('--repeat', type=int, default=1)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    results = []
    sides = a.side if a.script == 'turn' else [None]
    for rep in range(a.repeat):
        for side, config in itertools.product(sides, a.configs):
            spec = script(a.script, side or 1, a.button)
            core, *fixes = config.split('+')
            states.load(a.state)
            time.sleep(a.settle)
            with Debugger(a.port).connect() as d:
                d.release_all()
                applied = wordfix.apply(d, core, set(fixes))
                go, samples = play(d, spec)
            m = metrics(go, samples)
            head = {'config': config, 'side': side, 'repeat': rep}
            results.append({**head, 'go': go, 'writes': len(applied['writes']), 'metrics': m,
                            'samples': [{k: s[k] for k in ('t', 'v', 'frame', 'pos', *WORDS)} for s in samples]})
            print(json.dumps({**head, **{k: v for k, v in m.items() if k != 'atS'}}), flush=True)
    (a.out / 'board.json').write_text(json.dumps({'state': a.state, 'script': a.script, 'button': a.button,
                                                  'results': results}, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
