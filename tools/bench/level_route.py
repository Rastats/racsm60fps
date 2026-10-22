#!/usr/bin/env python3
"""Reach any level from a fresh boot by redirecting the LEVEL_01 module path.

The main module keeps one 40-byte path per level module
(`disc0:/PSP_GAME/USRDIR/BIN/LEVEL_NN.PRX`, BOOT.BIN file offset 0x3A05C for
LEVEL_01). A new game loads the LEVEL_01 entry; rewriting its two digits in RAM
loads another module instead, and that module loads its own art WAD
(`ART/LEVELS/level02/DATA/jungleruins.mb.wad` is a string of LEVEL_02.PRX).
The game state stays the new-game one: wrench, Blaster and Bomb Glove owned.

OBSERVED 2026-10-22: `go --to 02` from boot reaches Ryllus (rcp1 0x484B00,
base 0x09139D00, the same base as Pokitaru), playable after the arrival
cutscene. Other targets are untested.

  go --to NN      redirect, press through the frontend until the module is
                  resident (advance_to_level.py), then restore the entry
  redirect --to NN / restore / show

Run it right after `ppsspp_bench.py launch` (the frontend must still be on
screen: a level already started is not reloaded).
"""
import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ppsspp_bench import Debugger, DEFAULT_PORT, BenchError  # noqa: E402

NEEDLE = b'disc0:/PSP_GAME/USRDIR/BIN/LEVEL_'
ENTRY = 40


def find_table(d):
    """Address of the LEVEL_01 path entry inside the main module (`mcp`)."""
    mcp = d.module('mcp')
    lo, hi = mcp['address'], mcp['address'] + mcp['size']
    hits = []
    for a in range(lo, hi, 0x40000):
        n = min(0x40000 + len(NEEDLE), hi - a)
        blk = d.read(a, n)
        i = blk.find(NEEDLE)
        while i >= 0:
            hits.append(a + i)
            i = blk.find(NEEDLE, i + 1)
    hits = sorted(set(hits))
    # entries are 40 bytes apart; the first one after FRONTEND is LEVEL_01 (or its redirect)
    run = [h for h in hits if h + ENTRY in hits or h - ENTRY in hits]
    if not run:
        raise BenchError('level path table not found in mcp')
    return run[0]


def entry(d, addr):
    return d.read(addr, ENTRY).split(b'\0')[0].decode()


def write_digits(d, addr, digits):
    pos = addr + len(NEEDLE)
    cur = d.read(pos, 2)
    if not cur.isdigit():
        raise BenchError(f'unexpected entry {entry(d, addr)!r}')
    w = pos & ~3
    buf = bytearray(d.read(w, 8))
    buf[pos - w:pos - w + 2] = digits.encode()
    d.call('memory.write', address=w, base64=base64.b64encode(bytes(buf)).decode())
    if d.read(pos, 2) != digits.encode():
        raise BenchError('read-back mismatch')


def level_size(stem):
    import levels
    for size, s in levels._sizes().items():
        if s == stem:
            return size
    raise BenchError(f'{stem}.PRX not found')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('action', choices=('go', 'redirect', 'restore', 'show'))
    ap.add_argument('--to', help='two-digit level number, e.g. 02')
    ap.add_argument('--timeout', type=float, default=300.0)
    a = ap.parse_args()
    if a.action in ('go', 'redirect') and not (a.to and len(a.to) == 2 and a.to.isdigit()):
        ap.error('--to NN is required')
    with Debugger(a.port).connect() as d:
        addr = find_table(d)
        if a.action == 'show':
            print(json.dumps({'entry': hex(addr), 'path': entry(d, addr)}))
            return 0
        write_digits(d, addr, '01' if a.action == 'restore' else a.to)
        print(json.dumps({'entry': hex(addr), 'path': entry(d, addr)}))
    if a.action != 'go':
        return 0
    size = level_size(f'LEVEL_{a.to}')
    r = subprocess.run([sys.executable, str(HERE / 'advance_to_level.py'), '--port', str(a.port),
                        '--size', hex(size), '--buttons', 'cross,start,cross', '--timeout', str(a.timeout)])
    with Debugger(a.port).connect() as d:
        write_digits(d, find_table(d), '01')
    return r.returncode


if __name__ == '__main__':
    raise SystemExit(main())
