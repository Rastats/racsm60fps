#!/usr/bin/env python3
"""Player damage A/B/C in emulated time: hit times, HP lost, post-hit suppression.

For each configuration: load the savestate, apply it with wordfix.py, stand
still (no input) and record every write to the player's health and to the
post-hit suppression counter with breakpoints (breakloop.py).

Player struct: module+0x337940. Health f32 +0x964 (writer 0x38700, `-= amount`),
max +0x968. Post-hit suppression counter +0x97C: the player receiver rejects
hits while it is nonzero; 0x39B74 decrements it once per player substep
(research/v2/damage-atlas-20261006/REPORT.md section 2.3). Since C1 already
runs one substep per 60 Hz frame, its duration in seconds should match A0.

Damage source: Crab (pump-1 group callback 0x126F28). The 2026-10-20 guess
0x1234D0 was the Gadgetron vendor. In `pokitaru-blaster` no crab sees Ratchet;
the state `ghidra-crab` puts him on the knoll at (33, 2.6, 21) where crabs 6-8
chase and attack (research/static/2026-10-22-ghidra-crab-elevator/REPORT.md).
`--crab-slots` also records each crab's state byte (moby +0x45): 0xB chase,
0xD attack. In state 0xD, 0x1254CC counts pvar(+0x58)+0x60 up once per call
and lands the hit when it reaches the float at 0x2CF3C8 (27.0; `crab` = 54.0),
so the time from entering 0xD to the HP write is the attack wind-up the
`crab` fix targets, separate from the approach (`nav`).

Usage:
  python tools/bench/damage_probe.py --port 60908 --instance <root>/emu/ppsspp-2 \
      --state ghidra-crab --crab-slots 6 7 8 --configs A0 C1 C1+crab --seconds 12 \
      --out D:/racsm60fps/work/runs/damage-001
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
import states  # noqa: E402
import wordfix  # noqa: E402
import levels  # noqa: E402
import entities  # noqa: E402

PLAYER = 0x337940                   # LEVEL_01; other levels: levels.py
HP, SUPPRESS = 0x964, 0x97C
CRAB_UPDATE, CRAB_STATE, CRAB_ATTACK = 0x126F28, 0x45, 0xD


def _f(u):
    return struct.unpack('<f', struct.pack('<I', u & 0xFFFFFFFF))[0]


def crab_mobys(d, base, slots):
    """Moby address of each Crab slot (pump-1 group with callback 0x126F28)."""
    for g in entities.groups(d, base):
        if g['callback'] == CRAB_UPDATE:
            return {k: g['entities'] + k * 0x80 for k in slots}
    raise SystemExit('no Crab group (callback 0x126F28) in this state')


def record(d, seconds, crab_slots=()):
    base, prof = levels.profile(d)
    pl = base + prof['player']          # crab constants stay LEVEL_01 only
    events = []

    def on_hp(t, old, new):
        events.append({'t': t, 'field': 'hp', 'old': round(_f(old), 4), 'new': round(_f(new), 4)})

    def on_sup(t, old, new):
        events.append({'t': t, 'field': 'suppress', 'old': old, 'new': new})

    def on_crab(slot):
        def cb(t, old, new):
            events.append({'t': t, 'field': f'crab{slot}', 'old': old & 0xFF, 'new': new})
        return cb

    loop = BreakLoop(d, base)
    loop.watch(pl + HP, on_hp)
    loop.watch(pl + SUPPRESS, on_sup)
    for slot, moby in crab_mobys(d, base, crab_slots).items() if crab_slots else ():
        loop.watch(moby + CRAB_STATE, on_crab(slot))   # byte store: sb at moby+0x45
    hp0 = _f(d.u32(pl + HP))
    start, end = loop.run(seconds)
    for e in events:
        e['s'] = round((e['t'] - start) / CPU_HZ, 4)
    return {'hp0': round(hp0, 4), 'hpMax': round(_f(d.u32(pl + HP + 4)), 4), 'events': events,
            'spanS': round((end - start) / CPU_HZ, 4)}


def metrics(rec):
    hits = [e for e in rec['events'] if e['field'] == 'hp' and e['new'] < e['old']]
    out = {'hits': len(hits), 'hitTimesS': [e['s'] for e in hits],
           'hpLost': [round(e['old'] - e['new'], 4) for e in hits]}
    # Suppression windows: from a write that raises the counter to the write that brings it to 0.
    windows, opened = [], None
    for e in rec['events']:
        if e['field'] != 'suppress':
            continue
        if e['new'] > e['old'] and opened is None:
            opened = e
        elif e['new'] == 0 and opened is not None:
            windows.append({'from': opened['s'], 'value': opened['new'], 'durationS': round(e['s'] - opened['s'], 4)})
            opened = None
    out['suppression'] = windows
    out['suppressionWrites'] = sum(1 for e in rec['events'] if e['field'] == 'suppress')
    # Crab attack wind-up: from the latest entry into state 0xD (any watched crab) to each hit.
    onsets = [e for e in rec['events'] if e['field'].startswith('crab') and e['new'] == CRAB_ATTACK]
    if onsets:
        out['attackOnsetsS'] = [(e['field'], e['s']) for e in onsets]
        out['windupS'] = [round(h['s'] - max(o['s'] for o in onsets if o['s'] <= h['s']), 4)
                          for h in hits if any(o['s'] <= h['s'] for o in onsets)]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--instance', default=str(DEFAULT_INSTANCE), help='PPSSPP instance that owns --port (states load there)')
    ap.add_argument('--state', required=True)
    ap.add_argument('--configs', nargs='+', required=True)
    ap.add_argument('--seconds', type=float, default=20.0, help='emulated seconds per run')
    ap.add_argument('--settle', type=float, default=1.0, help='wall seconds after loading the state')
    ap.add_argument('--crab-slots', type=int, nargs='*', default=[],
                    help='Crab slots whose state byte (moby +0x45) is recorded, e.g. 6 7 8 in ghidra-crab')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    results = []
    for config in a.configs:
        core, *fixes = config.split('+')
        states.load(a.state, a.instance)
        time.sleep(a.settle)
        with Debugger(a.port).connect() as d:
            d.release_all()
            applied = wordfix.apply(d, core, set(fixes))
            rec = record(d, a.seconds, a.crab_slots)
        m = metrics(rec)
        results.append({'config': config, 'writes': len(applied['writes']), 'metrics': m, **rec})
        print(json.dumps({'config': config, 'hp0': rec['hp0'], **m}), flush=True)
    (a.out / 'damage.json').write_text(json.dumps({'state': a.state, 'results': results}, indent=1) + '\n',
                                       encoding='utf-8')


if __name__ == '__main__':
    main()
