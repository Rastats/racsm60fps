#!/usr/bin/env python3
"""Pokitaru elevator (Lvl3Elevator) ride time per configuration, in emulated time.

Static map (research/static/2026-10-22-ghidra-crab-elevator/REPORT.md):
- update 0x156710 (pump-1 group callback), initializer 0x1562DC, reached only
  through the class descriptor (no direct caller); it runs when the level's
  mobys are created, so every savestate taken in Pokitaru already holds the
  per-call step.
- moby +0x45 state: 0 idle, 1 moving, 2 arrived (return trip), 3 waiting.
  The ride starts when the player stands on the elevator (module+0x337C68 ==
  moby, test 0x155E00).
- pvar = moby +0x54: +0x04 moveTime (10.0 s at Pokitaru), +0x08 progress,
  +0x0C step = (1/moveTime) * (1/30), written by the initializer (lui at
  0x1563E8). While moving, every update adds +0x0C to +0x08 and the ride ends
  when progress exceeds 1.0: 300 calls, 10 s at 30 Hz, 5 s at 60 Hz.
- The `elevator` fix rewrites that lui to build 1/60, so it only acts when the
  initializer runs again (bench pitfall 13): `preinit` arms an execute
  breakpoint on the initializer from a fresh boot and applies the
  configuration at the hit, before the step is computed.

Subcommands:
  ride     load a state (or use the live one with --live), apply each config
           with wordfix.py, put the player on the elevator (test-aid teleport)
           and time state 0 -> 1 -> 2/3 with a write breakpoint on +0x45.
  preinit  from a freshly launched instance still outside Pokitaru: press
           through menus and cutscenes until the initializer is hit with
           LEVEL_01 resident, apply the config there, report the step it
           computes. Save a state afterwards (states.py) to repeat rides.
           It cannot read the screen: on a fresh memstick drive the language
           screen, system dialogs (circle) and "New Game" by hand, then run it
           with --buttons cross,start. Move earlier saves aside first (README
           pitfall 17). 2026-10-22: C1+elevator applied here gave step 1/600
           and a 10.01 s ride (state ghidra-elev-c1fix).

Usage:
  python tools/bench/elevator_probe.py --port 60908 --instance <root>/emu/ppsspp-2 \
      ride --state pokitaru-blaster --configs A0 C1 --out <root>/work/runs/<new>
  python tools/bench/elevator_probe.py --port 60908 preinit --config C1+elevator
"""
import argparse
import json
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ppsspp_bench import Debugger, DEFAULT_INSTANCE, DEFAULT_PORT  # noqa: E402
from breakloop import BreakLoop, CPU_HZ  # noqa: E402
import entities  # noqa: E402
import states  # noqa: E402
import wordfix  # noqa: E402

UPDATE, INIT = 0x156710, 0x1562DC
STATE = 0x45
PVAR = 0x54
MOVE_TIME, PROGRESS, STEP = 0x04, 0x08, 0x0C
ON_TOP = 1.4          # teleport height above the moby origin (2026-10-22: lands on the platform)
LEVEL01_BASE = 0x09139D00   # without plugins (README); checked again at the hit
STATES = {0: 'idle', 1: 'moving', 2: 'arrived', 3: 'waiting'}


def _f(u):
    return struct.unpack('<f', struct.pack('<I', u & 0xFFFFFFFF))[0]


def elevator(d, base):
    for g in entities.groups(d, base):
        if g['callback'] == UPDATE:
            return g['entities']             # one instance at Pokitaru: slot 0
    raise SystemExit('no Lvl3Elevator group (callback 0x156710) in this state')


def fields(d, moby):
    pv = d.u32(moby + PVAR)
    return {'moby': hex(moby), 'state': d.read(moby + STATE, 1)[0],
            'pos': [round(v, 3) for v in struct.unpack('<3f', d.read(moby + 0x30, 12))],
            'moveTime': round(_f(d.u32(pv + MOVE_TIME)), 4), 'progress': round(_f(d.u32(pv + PROGRESS)), 5),
            'step': _f(d.u32(pv + STEP)), 'stepTimesMoveTimeX30': round(_f(d.u32(pv + STEP)) * _f(d.u32(pv + MOVE_TIME)) * 30, 4)}


def ride(d, seconds):
    """Time the ride from its start (state 0 -> 1) with one break per progress write.

    The first Pokitaru ride cannot be timed to its end: at progress 0.74 a story
    cutscene freezes the game and the level module is replaced (rcp1 size
    0x484B00, OBSERVED 2026-10-22). So the ride time is measured as the number
    of updates needed (1 / step, from the live step) times the measured update
    interval, and cross-checked against progress per emulated second. Keep
    `seconds` short enough to stay below 0.74 (3.5 s at 60 updates/s).
    """
    base = d.module('rcp1')['address']
    moby = elevator(d, base)
    before = fields(d, moby)
    if before['state'] != 0:
        raise SystemExit(f"elevator not idle at the start (state {before['state']}): use a state taken before riding")
    pv = d.u32(moby + PVAR)
    states_, progress = [], []
    loop = BreakLoop(d, base)
    loop.watch(moby + STATE, lambda t, old, new: states_.append({'t': t, 'old': old & 0xFF, 'new': new}))
    loop.watch(pv + PROGRESS, lambda t, old, new: progress.append((t, _f(new))))
    x, y, z = before['pos']
    entities.teleport(d, base, (x, y + ON_TOP, z))
    start, end = loop.run(seconds)
    for e in states_:
        e['s'] = round((e['t'] - start) / CPU_HZ, 4)
    out = {'before': before, 'after': fields(d, moby), 'states': states_, 'progressWrites': len(progress),
           'spanS': round((end - start) / CPU_HZ, 4)}
    if len(progress) >= 3:
        gaps = sorted(b[0] - a[0] for a, b in zip(progress, progress[1:]))
        interval = gaps[len(gaps) // 2] / CPU_HZ
        (t0, p0), (t1, p1) = progress[0], progress[-1]
        rate = (p1 - p0) / ((t1 - t0) / CPU_HZ)
        calls = 1.0 / before['step']
        out.update({'updateIntervalS': round(interval, 6), 'updatesPerS': round(1 / interval, 3),
                    'stepMeasured': (p1 - p0) / (len(progress) - 1), 'progressPerS': round(rate, 5),
                    'lastProgress': round(p1, 4), 'callsToFinish': round(calls, 2),
                    'rideS': round(calls * interval, 4), 'rideFromRateS': round(1 / rate, 4)})
    return out


def cmd_ride(a):
    a.out.mkdir(parents=True, exist_ok=False)
    results = []
    for config in a.configs:
        core, *fixes = config.split('+')
        if not a.live:
            states.load(a.state, a.instance)
            time.sleep(a.settle)
        with Debugger(a.port).connect() as d:
            d.release_all()
            applied = wordfix.apply(d, core, set(fixes))
            rec = ride(d, a.seconds)
        results.append({'config': config, 'writes': len(applied['writes']), **rec})
        print(json.dumps({'config': config, **{k: rec.get(k) for k in ('rideS', 'rideFromRateS', 'updatesPerS', 'stepMeasured', 'lastProgress')}, 'step': rec['before']['step'],
                          'moveTime': rec['before']['moveTime']}), flush=True)
    (a.out / 'elevator.json').write_text(json.dumps({'state': None if a.live else a.state, 'results': results},
                                                    indent=1) + '\n', encoding='utf-8')


def cmd_preinit(a):
    core, *fixes = a.config.split('+')
    buttons = [b for b in a.buttons.split(',') if b]
    bp = LEVEL01_BASE + INIT
    log = {'config': a.config, 'breakpoint': hex(bp), 'presses': 0, 'foreignHits': 0}
    with Debugger(a.port).connect() as d:
        d.add_cpu_breakpoint(bp)
        try:
            deadline, i = time.monotonic() + a.timeout, 0
            while True:
                if time.monotonic() > deadline:
                    raise SystemExit(json.dumps({'result': 'TIMEOUT', **log}))
                ev = d.wait_event('cpu.stepping', timeout=a.every)
                if ev is None:
                    d.press(buttons[i % len(buttons)], 3)
                    log['presses'] += 1
                    i += 1
                    continue
                pc = int(ev['pc'])
                mods = [m for m in d.modules() if m['name'] == 'rcp1']
                if pc == bp and mods and mods[0]['size'] == wordfix.LEVEL01_SIZE and mods[0]['address'] == LEVEL01_BASE:
                    break
                log['foreignHits'] += 1       # same address in another module, or another stop
                d.resume()
            moby = d.call('cpu.getReg', category=0, register=4)['uintValue']   # a0 = this moby
            log.update({'ticks': int(ev['ticks']), 'moby': hex(moby), 'stepBefore': _f(d.u32(d.u32(moby + PVAR) + STEP))})
        finally:
            d.remove_cpu_breakpoint(bp)
        applied = wordfix.apply(d, core, set(fixes))    # resumes the CPU
        time.sleep(2.0)
        log.update({'writes': len(applied['writes']), 'after': fields(d, moby)})
    print(json.dumps(log, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--instance', default=str(DEFAULT_INSTANCE), help='PPSSPP instance that owns --port (states load there)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('ride')
    r.add_argument('--state')
    r.add_argument('--live', action='store_true', help='use the running game instead of loading --state (one config)')
    r.add_argument('--configs', nargs='+', required=True)
    r.add_argument('--seconds', type=float, default=3.0, help='emulated seconds recorded per ride (stay below progress 0.74)')
    r.add_argument('--settle', type=float, default=1.0, help='wall seconds after loading the state')
    r.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('preinit')
    p.add_argument('--config', required=True)
    p.add_argument('--buttons', default='circle,start', help='buttons pressed in turn until the hit')
    p.add_argument('--every', type=float, default=3.0, help='seconds between presses')
    p.add_argument('--timeout', type=float, default=600.0)
    a = ap.parse_args()
    if a.cmd == 'ride' and not (a.live or a.state):
        ap.error('ride needs --state or --live')
    cmd_ride(a) if a.cmd == 'ride' else cmd_preinit(a)


if __name__ == '__main__':
    main()
