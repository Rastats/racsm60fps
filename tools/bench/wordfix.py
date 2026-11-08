#!/usr/bin/env python3
"""Apply or revert word-level fixes on the resident level without any plugin.

Reuses the definitions of tools/runtime/fixes.py (`DATA`: name -> (rva,
original word, fixed word)) and the C1 core of tools/runtime/pump-gate.py, so
nothing is duplicated. Those RVAs are LEVEL_01's; on another level the core and
fix sites come from the port of tools/bench/level_port.py (via levels.py), and a
fix that did not port is refused instead of being written blind. Only the DATA family is supported: wrapper, stub and
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
from breakloop import is_branch  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pg = _load('pump_gate', 'tools/runtime/pump-gate.py')
fx = _load('fixes', 'tools/runtime/fixes.py')
DATA = fx.DATA
LEVEL01_SIZE = pg.MODULE_SIZE


def expand(fixes, native=None):
    """Resolve fixes.py group names ('camera', ALIASES) to DATA names; refuse anything else.

    `native` is the resident level's {group: [word names]} of its own candidate
    fixes (levels.py NATIVE). Before 2026-10-20 apply() skipped unknown names
    silently, so 'C1+camera' ran as plain C1.
    """
    out = set(fixes)
    native = native or {}
    for name, members in native.items():
        if name in out:
            out = (out - {name}) | set(members)
    if 'camera' in out:
        out = (out - {'camera'}) | set(fx.CAMERA)
    for name, members in fx.ALIASES.items():
        if name in out:
            out = (out - {name}) | set(members)
    unknown = out - set(DATA) - {m for ms in native.values() for m in ms}
    if unknown:
        raise BenchError(f'not a word-level fix: {sorted(unknown)} (wrappers/stubs need fixes.py and InterpGate)')
    return out


def core_words(base, prof):
    """{rva: (A0 word, C1 word)} of the C1 core for a ported level (levels.py).

    vblank: the relocated `jal` -> nop; delta: `lui rX,0x3D08` -> 0x3C88;
    loop: `slti rX,rY,2` -> 1, left alone where the original already holds 1
    (LEVEL_16-20, docs/TECHNICAL_OVERVIEW.md).
    """
    f = prof['core_file']
    vb = f['vblank']
    if vb >> 26 != 3:
        raise BenchError(f'{prof["stem"]}: vblank site holds 0x{vb:08X}, not a jal')
    jal_rt = 0x0C000000 | (((base + ((vb & 0x03FFFFFF) << 2)) >> 2) & 0x03FFFFFF)
    return {prof['core']['vblank']: (jal_rt, 0),
            prof['core']['delta']: (f['delta'], (f['delta'] & 0xFFFF0000) | 0x3C88),
            prof['core']['loop']: (f['loop'], (f['loop'] & 0xFFFF0000) | 1)}


def apply(d, core, fixes):
    mod = d.module('rcp1')
    base = mod['address']
    want = {}
    if mod['size'] == LEVEL01_SIZE:
        fixes = expand(fixes)
        exp = pg.expected(base, core)
        a0, c1 = pg.expected(base, 'A0'), pg.expected(base, 'C1')
        for rva in (pg.VBLANK, pg.DELTA, pg.LOOP):
            want[rva] = ({a0[rva], c1[rva]}, exp[rva])     # core word: either A0 or C1 accepted as old value
        table = DATA
    else:
        # Other level: core and fixes ported from LEVEL_01 by levels.py / level_port.py.
        import levels
        prof = levels.profile_for_size(mod['size'])
        fixes = expand(fixes, prof.get('native'))
        for rva, (w_a0, w_c1) in core_words(base, prof).items():
            want[rva] = ({w_a0, w_c1}, w_c1 if core == 'C1' else w_a0)
        table = prof['fixes']
        missing = fixes - set(table)
        if missing:
            raise BenchError(f'{prof["stem"]}: fixes not ported from LEVEL_01: {sorted(missing)}')
    for name in table:
        rva, orig, new = table[name]
        want[rva] = ({orig, new}, new if name in fixes else orig)
    writes, refresh = [], 0
    if not d.cpu().get('stepping'):    # already stopped (e.g. at a breakpoint): no ack would come
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
    # Names are resolved by apply(), which knows the resident level and its native groups.
    fixes = {f for f in a.fix.split(',') if f}
    if a.core == 'A0' and fixes:
        ap.error('A0 is the original game: no fixes')
    with Debugger(a.port).connect() as d:
        try:
            print(json.dumps(apply(d, a.core, fixes)))
        except BenchError as e:
            ap.error(str(e))


if __name__ == '__main__':
    main()
