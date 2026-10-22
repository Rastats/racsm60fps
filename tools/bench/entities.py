#!/usr/bin/env python3
"""Pump-1 entities of LEVEL_01 with positions, nearest first; test-aid teleport.

Layout (tools/runtime/group-census.py and the 2026-09-30 session log):
manager pointer at module+0x2CA0D0; groups at manager+0x34 (count +0x38),
stride 0x50; group +0x0C entity array (stride 0x80), +0x1C update callback,
+0x3C capacity. Entity position f32 x/y/z at +0x30 (read by the pump's
distance check). Player position: module+0x337940 +0x30.

Class names need the research atlas, absent from the public repository, so
groups are identified by callback RVA. Guesses from code layout were wrong
on 2026-10-20 (state pokitaru-blaster, checked by teleport + window capture):
  0x1234D0  Gadgetron vendor, not a crab
  0x126F28, 0x122820  entities in the sea, not crabs
  0x155CE4  not a solid platform (the player falls through at its +0x30)
Crab and Lvl3Elevator groups are still UNKNOWN.

Usage:
  python tools/bench/entities.py list [--group 0x1234D0] [--near 30]
  python tools/bench/entities.py teleport --to X Y Z     # TEST AID, not a parity change
"""
import argparse
import json
import math
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa: E402
import levels  # noqa: E402

MANAGER = 0x2CA0D0                  # LEVEL_01; other levels: levels.py
PLAYER, POS = 0x337940, 0x30


def _rva(d, name):
    return levels.profile(d)[1][name]


def groups(d, base):
    mgr = d.u32(base + _rva(d, 'entity_manager'))
    arr, n = d.u32(mgr + 0x34), d.u32(mgr + 0x38)
    out = []
    for i in range(n):
        g = d.read(arr + i * 0x50, 0x50)
        ents, cb, cap = struct.unpack_from('<I', g, 0x0C)[0], struct.unpack_from('<I', g, 0x1C)[0], \
            struct.unpack_from('<I', g, 0x3C)[0]
        rva = cb - base if base <= cb < base + 0x1000000 else None
        out.append({'i': i, 'callback': rva, 'entities': ents, 'capacity': cap})
    return out


def player_pos(d, base):
    return list(struct.unpack('<3f', d.read(base + _rva(d, 'player') + POS, 12)))


def listing(d, base, only=None, near=None):
    p = player_pos(d, base)
    rows = []
    for g in groups(d, base):
        if only is not None and g['callback'] != only:
            continue
        if not g['entities'] or g['capacity'] > 512:
            continue
        for k in range(g['capacity']):
            e = g['entities'] + k * 0x80
            x, y, z = struct.unpack('<3f', d.read(e + 0x30, 12))
            if not all(math.isfinite(v) for v in (x, y, z)):
                continue
            dist = math.dist(p, (x, y, z))
            if near is None or dist <= near:
                rows.append({'group': g['i'], 'callback': hex(g['callback']) if g['callback'] is not None else None,
                             'slot': k, 'entity': hex(e), 'pos': [round(x, 3), round(y, 3), round(z, 3)],
                             'dist': round(dist, 2)})
    rows.sort(key=lambda r: r['dist'])
    return {'player': [round(v, 3) for v in p], 'entities': rows}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    sub = ap.add_subparsers(dest='cmd', required=True)
    ls = sub.add_parser('list')
    ls.add_argument('--group', type=lambda s: int(s, 0))
    ls.add_argument('--near', type=float)
    tp = sub.add_parser('teleport')
    tp.add_argument('--to', type=float, nargs=3, required=True)
    a = ap.parse_args()
    with Debugger(a.port).connect() as d:
        base = d.module('rcp1')['address']
        if a.cmd == 'list':
            print(json.dumps(listing(d, base, a.group, a.near), indent=1))
        else:
            before = player_pos(d, base)
            d.pause()
            try:
                for k, v in enumerate(a.to):
                    d.write_u32(base + _rva(d, 'player') + POS + 4 * k, struct.unpack('<I', struct.pack('<f', v))[0])
            finally:
                d.resume()
            print(json.dumps({'before': before, 'after': player_pos(d, base)}))


if __name__ == '__main__':
    main()
