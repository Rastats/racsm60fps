#!/usr/bin/env python3
"""Pump-1 entities of LEVEL_01 with positions, nearest first; test-aid teleport.

Layout (tools/runtime/group-census.py and the 2026-09-30 session log):
manager pointer at module+0x2CA0D0; groups at manager+0x34 (count +0x38),
stride 0x50; group +0x0C entity array (stride 0x80), +0x1C update callback,
+0x3C capacity. Entity position f32 x/y/z at +0x30 (read by the pump's
distance check). Player position: module+0x337940 +0x30.

Class names: research/v2/decomp-summary/level01-class-updates.json maps
each class to its update (= group callback). Checked live on 2026-10-22
(research/static/2026-10-22-ghidra-crab-elevator/REPORT.md):
  0x126F28  Crab (58 slots; the 2026-10-20 "entities in the sea" were real
            crabs. Crabs stay idle (state +0x45 = 1 or 4) until the player
            enters their territory volume, pvar(+0x54)+0x10)
  0x156710  Lvl3Elevator (1 instance, the Pokitaru elevator)
  0x1234D0  Gadgetron vendor (2026-10-20)
`list` skips slots whose active bit is clear unless --all is given.

Teleport writes every player position copy (+0x30, +0x70, +0x26C, +0x338,
+0xA88, and the y words +0x2D0/+0x2D4). Writing +0x30 alone keeps x/z but the
game rebuilds y from the copies; at another height the player falls through
the ground and respawns (2026-10-22). Aim slightly above the ground.

Usage:
  python tools/bench/entities.py list [--group 0x1234D0] [--near 30]
  python tools/bench/entities.py teleport --to X Y Z     # TEST AID, not a parity change
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

MANAGER = 0x2CA0D0
PLAYER, POS = 0x337940, 0x30
POS_COPIES = (0x30, 0x70, 0x26C, 0x338, 0xA88)   # x, y, z triples
Y_COPIES = (0x2D0, 0x2D4)
ACTIVE = 0x1                                    # moby +0x64 bit 0


def groups(d, base):
    mgr = d.u32(base + MANAGER)
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
    return list(struct.unpack('<3f', d.read(base + PLAYER + POS, 12)))


def listing(d, base, only=None, near=None, everything=False):
    p = player_pos(d, base)
    rows = []
    for g in groups(d, base):
        if only is not None and g['callback'] != only:
            continue
        if not g['entities'] or g['capacity'] > 512:
            continue
        for k in range(g['capacity']):
            e = g['entities'] + k * 0x80
            if not everything and not d.u32(e + 0x64) & ACTIVE:
                continue
            x, y, z = struct.unpack('<3f', d.read(e + 0x30, 12))
            if not all(math.isfinite(v) for v in (x, y, z)):
                continue
            dist = math.dist(p, (x, y, z))
            if near is None or dist <= near:
                rows.append({'group': g['i'], 'callback': hex(g['callback']) if g['callback'] is not None else None,
                             'slot': k, 'entity': hex(e), 'state': d.read(e + 0x45, 1)[0], 'pos': [round(x, 3), round(y, 3), round(z, 3)],
                             'dist': round(dist, 2)})
    rows.sort(key=lambda r: r['dist'])
    return {'player': [round(v, 3) for v in p], 'entities': rows}


def teleport(d, base, to):
    """TEST AID: move the player to `to` (x, y, z); returns the position before."""
    pl = base + PLAYER
    before = player_pos(d, base)
    words = [struct.unpack('<I', struct.pack('<f', v))[0] for v in to]
    d.pause()
    try:
        for off in POS_COPIES:
            for k in range(3):
                d.write_u32(pl + off + 4 * k, words[k])
        for off in Y_COPIES:
            d.write_u32(pl + off, words[1])
    finally:
        d.resume()
    return before


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    sub = ap.add_subparsers(dest='cmd', required=True)
    ls = sub.add_parser('list')
    ls.add_argument('--group', type=lambda s: int(s, 0))
    ls.add_argument('--near', type=float)
    ls.add_argument('--all', action='store_true', help='include slots whose active bit is clear')
    tp = sub.add_parser('teleport')
    tp.add_argument('--to', type=float, nargs=3, required=True)
    a = ap.parse_args()
    with Debugger(a.port).connect() as d:
        base = d.module('rcp1')['address']
        if a.cmd == 'list':
            print(json.dumps(listing(d, base, a.group, a.near, a.all), indent=1))
        else:
            before = teleport(d, base, a.to)
            time.sleep(0.5)
            print(json.dumps({'before': before, 'after': player_pos(d, base)}))


if __name__ == '__main__':
    main()
