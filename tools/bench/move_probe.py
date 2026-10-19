#!/usr/bin/env python3
"""Player movement A/B/C in emulated time: walk and jump trajectories.

For each configuration: load the savestate, apply it with wordfix.py, then
play a frame-locked input script (breakloop.py) and record the player
position once per game frame. Scripts are written in vblanks from the first
frame boundary, so A0 (2 vblanks per frame) and C1 (1 per frame) get the
same input at the same emulated times.

Position: player module+0x337940, vector +0x30/+0x34/+0x38 (static map in
research/v2/pokitaru/player-clock-socle-map.md; live check 2026-10-19:
+0x30 and +0x38 change while walking on flat ground, +0x34 does not).
Samples are taken at the frame counter write, so A0 samples at 30 Hz and C1
at 60 Hz; metrics are computed per config in emulated seconds.

Scripts (vblank = 1001/60000 s):
  walk      stick forward for 120 vblanks (2.0 s), then neutral to 180
  jump      cross for 4 vblanks, then neutral to 150
  walkjump  stick forward for 180 vblanks, cross for 4 vblanks at 60

Usage:
  python tools/bench/move_probe.py --state pokitaru-blaster --script walk \
      --configs A0 C1 --out D:/racsm60fps/work/runs/move-walk-001
"""
import argparse
import json
import math
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa: E402
from breakloop import BreakLoop, CPU_HZ  # noqa: E402
import states  # noqa: E402
import wordfix  # noqa: E402

VBLANK_TICKS = 3_703_700
VBLANK_S = 1001 / 60000
PLAYER, POS = 0x337940, 0x30
SCRIPTS = {
    # name: (total vblanks, [(start, end, input)]); input held on [start, end).
    # 'stick': True means the stick at --angle (0 = up, 90 = right), full deflection.
    'walk': (180, [(0, 120, {'stick': True})]),
    'jump': (150, [(0, 4, {'cross': True})]),
    'walkjump': (180, [(0, 180, {'stick': True}), (60, 64, {'cross': True})]),
}


def wanted(script, v, angle):
    """Input at vblank index v: ((stick x, stick y), frozenset of held buttons)."""
    stick, held = (0.0, 0.0), set()
    for start, end, inp in SCRIPTS[script][1]:
        if start <= v < end:
            if inp.get('stick'):
                a = math.radians(angle)
                stick = (round(math.sin(a), 6), round(math.cos(a), 6))
            held |= {k for k in inp if k != 'stick'}
    return stick, frozenset(held)


def play(d, script, angle=0.0):
    base = d.module('rcp1')['address']
    pos_addr = base + PLAYER + POS
    total = SCRIPTS[script][0]
    buttons = sorted({k for _, _, inp in SCRIPTS[script][1] for k in inp if k != 'stick'})
    samples, cur = [], {'stick': None, 'held': None}
    t0 = []

    def on_frame(t, value):
        if value is None:
            return
        if not t0:
            t0.append(t)
        v = round((t - t0[0]) / VBLANK_TICKS)
        x, y, z = struct.unpack('<3f', d.read(pos_addr, 12))
        samples.append({'v': v, 't': t - t0[0], 'frame': value, 'pos': [x, y, z]})
        stick, held = wanted(script, v, angle) if v < total else ((0.0, 0.0), frozenset())
        if stick != cur['stick']:
            d.stick(*stick)
            cur['stick'] = stick
        if held != cur['held']:
            d.buttons(**{b: b in held for b in buttons})
            cur['held'] = held

    def release():
        d.stick(0.0, 0.0)
        if buttons:
            d.buttons(**{b: False for b in buttons})

    loop = BreakLoop(d, base)
    loop.every_frame(on_frame)
    loop.at_end(release)
    # One vblank beyond the script so the last scheduled frame is sampled.
    loop.run((total + 1) * VBLANK_S + 0.05)
    return samples


def metrics(samples, script):
    """Distances in game units; times as vblank indices (v) from the first frame boundary.

    A0 samples every 2 vblanks and C1 every vblank, both from v = 0, so values
    read at even v compare the same emulated instant.
    """
    p0 = samples[0]['pos']
    out = {'samples': len(samples)}
    path = [0.0]
    for a, b in zip(samples, samples[1:]):
        path.append(path[-1] + math.hypot(b['pos'][0] - a['pos'][0], b['pos'][2] - a['pos'][2]))
    vs = [s['v'] for s in samples]

    def at(series, v_target):      # value at the last sample with v <= v_target
        best = None
        for v, val in zip(vs, series):
            if v <= v_target:
                best = val
        return best

    out['horizontalDisplacementEnd'] = round(math.hypot(samples[-1]['pos'][0] - p0[0],
                                                        samples[-1]['pos'][2] - p0[2]), 4)
    out['pathLengthEnd'] = round(path[-1], 4)
    if script in ('walk', 'walkjump'):
        out['pathAtV'] = {v: round(at(path, v), 4) for v in (10, 20, 30, 40, 60, 90, 120)}
        held_end = SCRIPTS[script][1][0][1]
        moving = [i for i in range(1, len(samples)) if path[i] - path[i - 1] > 1e-4 and vs[i] <= held_end]
        stalled = next((vs[i] for i in range(1, len(samples))
                        if vs[i] < held_end and moving and vs[i] > vs[moving[0]]
                        and path[i] - path[i - 1] <= 1e-4), None)
        out['stalledAtV'] = stalled        # first frame without motion while the stick is held
    if script == 'walk':
        out['stopDistanceAfterRelease'] = round(path[-1] - at(path, 120), 4)
    ys = [s['pos'][1] for s in samples]
    i_max = max(range(len(ys)), key=lambda i: ys[i])
    out['yMaxAboveStart'] = round(ys[i_max] - ys[0], 4)
    out['yMaxAtV'] = vs[i_max]
    if ys[i_max] - ys[0] > 0.05:
        lift = next((vs[i] for i in range(len(ys)) if ys[i] > ys[0] + 0.01), None)
        land = next((vs[i] for i in range(i_max, len(ys)) if ys[i] <= ys[0] + 0.01), None)
        out['airborneFromV'], out['landedAtV'] = lift, land
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--state', required=True)
    ap.add_argument('--script', choices=sorted(SCRIPTS), required=True)
    ap.add_argument('--configs', nargs='+', required=True)
    ap.add_argument('--angles', type=float, nargs='+', default=[0.0],
                    help='stick directions in degrees (0 = up, 90 = right); one run per angle and config')
    ap.add_argument('--settle', type=float, default=1.0, help='wall seconds after loading the state')
    ap.add_argument('--repeat', type=int, default=1)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    results = []
    for rep in range(a.repeat):
        for angle in a.angles:
            for config in a.configs:
                core, *fixes = config.split('+')
                states.load(a.state)
                time.sleep(a.settle)
                with Debugger(a.port).connect() as d:
                    d.release_all()
                    applied = wordfix.apply(d, core, set(fixes))
                    samples = play(d, a.script, angle)
                m = metrics(samples, a.script)
                results.append({'config': config, 'angle': angle, 'repeat': rep,
                                'writes': len(applied['writes']), 'metrics': m, 'samples': samples})
                print(json.dumps({'config': config, 'angle': angle, 'repeat': rep, **m}), flush=True)
    (a.out / 'move.json').write_text(json.dumps({'state': a.state, 'script': a.script,
                                                 'results': results}, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
