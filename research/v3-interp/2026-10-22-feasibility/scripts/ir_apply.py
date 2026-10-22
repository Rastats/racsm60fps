#!/usr/bin/env python3
"""Arm or disarm the InterpRender plugin (../prx) on a resident LEVEL_01.

The plugin must be loaded by PPSSPP (memstick/PSP/PLUGINS/InterpRender). This
script, through the debugger:
  1. locates the InterpRender module and checks that its first code word matches
     the built ELF (symbols from ../prx/build/symbols.txt are module offsets);
  2. writes ir_cfg (pump 1, render, entity-manager pointer address);
  3. applies the three C1 core words (as tools/runtime/pump-gate.py), guarded;
  4. redirects 0x15230 (jal pump 1) to ir_pump and 0x15AB0 (jal render) to
     ir_render, each guarded by its original word;
  5. sets the mode: 0 pass-through, 1 G1 gate only, 2 gate + interpolation.
`--off` restores both call sites and sets mode 0 (the C1 core stays).

Usage:
  python ir_apply.py --port 60909 --mode 2
  python ir_apply.py --port 60909 --status
  python ir_apply.py --port 60909 --off
"""
import argparse
import json
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PRX = HERE.parent / 'prx'
BUILD = os.environ.get('IR_BUILD', 'build')    # build-v1: IR-v1, the build held by the interp-ir-pokitaru state
sys.path.insert(0, str(REPO / 'tools/bench'))
from ppsspp_bench import Debugger, BenchError  # noqa: E402

LEVEL01_SIZE = 0x46B900
PUMP1, RENDER, MANAGER = 0x6B7F4, 0x156DC, 0x2CA0D0
SITE_PUMP, SITE_RENDER = 0x15230, 0x15AB0
VBLANK, VBLANK_STUB = 0x96650, 0x1BF424
# C1 core (tools/runtime/pump-gate.py): rva -> (original, C1); the VBlank word is checked against jal stub
CORE = {0x151E0: (0x3C043D08, 0x3C043C88), 0x2FCFC: (0x2A240002, 0x2A240001)}
STAT_NAMES = ('runs', 'skips', 'blended_frames', 'blended_matrices', 'snapped', 'exempted',
              'entries', 'snapshot_overflow', 'restores', 'span_base', 'restore_overflow', 'pad')


def jal(target):
    return 0x0C000000 | ((target >> 2) & 0x03FFFFFF)


def symbols():
    out = {}
    for line in (PRX / BUILD / 'symbols.txt').read_text(encoding='ascii').splitlines():
        off, kind, name = line.split()
        out[name] = int(off, 16)
    return out


def code_words(n=64):
    """First n words of .text in the built ELF (section offset from the section header table)."""
    d = (PRX / BUILD / 'interp_render.elf').read_bytes()
    shoff, = struct.unpack_from('<I', d, 0x20)
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', d, 0x2E)
    secs = [struct.unpack_from('<10I', d, shoff + i * shentsize) for i in range(shnum)]
    stro = secs[shstrndx][4]
    for s in secs:
        name = d[stro + s[0]:d.index(b'\0', stro + s[0])]
        if name == b'.text':
            return struct.unpack_from('<%dI' % n, d, s[4])
    raise BenchError('no .text')


def locate(d):
    mods = {m['name']: m for m in d.modules()}
    if 'InterpRender' not in mods:
        raise BenchError('InterpRender plugin not resident')
    lvl = mods.get('rcp1')
    if not lvl or lvl['size'] != LEVEL01_SIZE:
        raise BenchError('LEVEL_01 must be resident')
    ir = mods['InterpRender']['address']
    # compare the branch words (beq/bne/blez/bgtz, never relocated) of the first 64 code words
    elf, live = code_words(), d.u32(ir, 64)
    checked = [i for i, w in enumerate(elf) if (w >> 26) in (4, 5, 6, 7)]
    if not checked or any(elf[i] != live[i] for i in checked):
        raise BenchError('InterpRender code does not match the built ELF')
    sym = {k: ir + v for k, v in symbols().items()}
    return lvl['address'], sym


def status(d, sym):
    cfg = d.u32(sym['ir_cfg'], 8)
    st = d.u32(sym['ir_stat'], 12)
    return {'mode': cfg[0], 'cfg': [hex(x) for x in cfg], 'stat': dict(zip(STAT_NAMES, st))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--mode', type=int, choices=(0, 1, 2))
    g.add_argument('--status', action='store_true')
    g.add_argument('--off', action='store_true')
    a = ap.parse_args()
    with Debugger(a.port).connect() as d:
        base, sym = locate(d)
        rec = {'base': hex(base), 'symbols': {k: hex(v) for k, v in sym.items()}}
        if a.status:
            rec.update(status(d, sym))
            print(json.dumps(rec, indent=1))
            return
        orig = {SITE_PUMP: jal(base + PUMP1), SITE_RENDER: jal(base + RENDER)}
        hooked = {SITE_PUMP: jal(sym['ir_pump']), SITE_RENDER: jal(sym['ir_render'])}
        if a.off:
            d.pause()
            try:
                d.write_u32(sym['ir_cfg'], 0)
                for rva in (SITE_PUMP, SITE_RENDER):
                    if d.u32(base + rva) == hooked[rva]:
                        d.write_u32(base + rva, orig[rva], expect=hooked[rva])
            finally:
                d.resume()
            rec.update(status(d, sym))
            print(json.dumps(rec, indent=1))
            return
        d.pause()
        try:
            core = {VBLANK: (jal(base + VBLANK_STUB), 0), **CORE}
            for rva, (o, n) in core.items():
                w = d.u32(base + rva)
                if w not in (o, n):
                    raise BenchError(f'unexpected core word at +0x{rva:X}: 0x{w:08X}')
            for rva, (o, n) in core.items():
                if d.u32(base + rva) != n:
                    d.write_u32(base + rva, n, expect=o)
            rec['core'] = 'C1'
            d.write_u32(sym['ir_cfg'] + 4, base + PUMP1)
            d.write_u32(sym['ir_cfg'] + 8, base + RENDER)
            d.write_u32(sym['ir_cfg'] + 12, base + MANAGER)
            for rva in (SITE_PUMP, SITE_RENDER):
                old = d.u32(base + rva)
                if old not in (orig[rva], hooked[rva]):
                    raise BenchError(f'unexpected word at +0x{rva:X}: 0x{old:08X}')
                if old != hooked[rva]:
                    d.write_u32(base + rva, hooked[rva], expect=orig[rva])
            d.write_u32(sym['ir_cfg'], a.mode)
        finally:
            d.resume()
        rec.update(status(d, sym))
        print(json.dumps(rec, indent=1))


if __name__ == '__main__':
    main()
