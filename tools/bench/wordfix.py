#!/usr/bin/env python3
"""Apply or revert word-level fixes on LEVEL_01 without any plugin.

Reuses the definitions of tools/runtime/fixes.py (`DATA`: name -> (rva,
original word, fixed word)) and the C1 core of tools/runtime/pump-gate.py, so
nothing is duplicated. Only the DATA family is supported: wrapper, stub and
telemetry fixes need the InterpGate plugin and stay with fixes.py.

Each write is guarded by the expected old word and verified by read-back, with
the CPU paused. When the patched word sits in a branch delay slot, the
preceding branch is rewritten with its own value afterwards: PPSSPP's JIT
compiles a delay slot with its branch and only recompiles when the branch
word itself changes (docs/WEAPONS_PARITY_2026-10-02.md, mechanism 2).

Usage:
  python tools/bench/wordfix.py --core C1 --fix weapondt
  python tools/bench/wordfix.py --core A0            # original game, all listed fixes reverted
  python tools/bench/wordfix.py --list
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from ppsspp_bench import Debugger, DEFAULT_PORT, BenchError  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pg = _load('pump_gate', 'tools/runtime/pump-gate.py')
fx = _load('fixes', 'tools/runtime/fixes.py')
DATA = fx.DATA
LEVEL01_SIZE = pg.MODULE_SIZE


def is_branch(word):
    op = word >> 26
    if op in (2, 3):                       # j, jal
        return True
    if op == 0 and (word & 0x3F) in (8, 9):  # jr, jalr
        return True
    if op in (4, 5, 6, 7, 20, 21, 22, 23):   # beq, bne, blez, bgtz (+ likely)
        return True
    if op == 1 and ((word >> 16) & 0x1F) in (0, 1, 2, 3, 16, 17, 18, 19):  # regimm branches
        return True
    if op == 17 and ((word >> 21) & 0x1F) == 8:  # bc1x
        return True
    return False


def apply(d, core, fixes):
    mod = d.module('rcp1')
    if mod['size'] != LEVEL01_SIZE:
        raise BenchError('LEVEL_01 (Pokitaru) must be the resident level')
    base = mod['address']
    want = {}
    exp = pg.expected(base, core)
    a0, c1 = pg.expected(base, 'A0'), pg.expected(base, 'C1')
    for rva in (pg.VBLANK, pg.DELTA, pg.LOOP):
        want[rva] = ({a0[rva], c1[rva]}, exp[rva])     # core word: either A0 or C1 accepted as old value
    for name in DATA:
        rva, orig, new = DATA[name]
        want[rva] = ({orig, new}, new if name in fixes else orig)
    writes, refresh = [], 0
    d.pause()
    try:
        # Phase 1: check every guard before writing anything (all-or-nothing).
        plan = []
        for rva, (allowed, value) in sorted(want.items()):
            old = d.u32(base + rva)
            if 0 in allowed and not fx._RAW.exists():
                raise BenchError(f'fix at +0x{rva:X} has no known original word: reference PRX missing ({fx._RAW})')
            if old not in allowed:
                raise BenchError(f'unexpected word at +0x{rva:X}: 0x{old:08X}')
            if old != value:
                plan.append((rva, old, value))
        # Phase 2: write; on any failure restore what was written.
        try:
            for rva, old, value in plan:
                d.write_u32(base + rva, value, expect=old)
                writes.append({'rva': hex(rva), 'before': hex(old), 'after': hex(value)})
                prev = d.u32(base + rva - 4)
                if is_branch(prev):
                    d.write_u32(base + rva - 4, prev)     # force JIT recompilation of branch + slot
                    refresh += 1
        except Exception:
            for w in reversed(writes):
                d.write_u32(base + int(w['rva'], 16), int(w['before'], 16))
            raise
    finally:
        d.resume()
    return {'base': hex(base), 'core': core, 'fixes': sorted(fixes), 'writes': writes, 'jitRefresh': refresh}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--core', choices=('A0', 'C1'))
    ap.add_argument('--fix', default='', help='comma-separated DATA fix names (see --list)')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    if a.list:
        for name, (rva, orig, new) in sorted(DATA.items()):
            print(f'{name:16s} +0x{rva:06X} 0x{orig:08X} -> 0x{new:08X}')
        return
    if not a.core:
        ap.error('--core is required')
    fixes = {f for f in a.fix.split(',') if f}
    unknown = fixes - set(DATA)
    if unknown:
        ap.error(f'not a word-level fix: {sorted(unknown)} (wrappers/stubs need fixes.py and InterpGate)')
    if a.core == 'A0' and fixes:
        ap.error('A0 is the original game: no fixes')
    with Debugger(a.port).connect() as d:
        print(json.dumps(apply(d, a.core, fixes)))


if __name__ == '__main__':
    main()
