#!/usr/bin/env python3
"""Per-level constants for the bench, keyed by the resident `rcp1` module size.

LEVEL_01 (Pokitaru) keeps the hand-checked constants the bench was built on.
Any other level is ported from them offline by level_port.py (masked byte
match of the extracted PRX files under <root>/game/iso) and cached per process.

A profile holds:
  stem, size              module name (LEVEL_02) and rcp1 load size
  core                    {'vblank','delta','loop'} RVAs of the C1 core
  core_file               {name: unrelocated word in the PRX}
  frame_counter, player, ammo_base, entity_manager    data RVAs
  fixes                   {fixes.DATA name: (rva, original, fixed)} for the
                          sites ported with an identical original word only

How the bench reaches a level other than Pokitaru (2026-10-22): the main module
keeps a table of 40-byte paths `disc0:/PSP_GAME/USRDIR/BIN/LEVEL_NN.PRX`
(BOOT.BIN file offset 0x3A05C for LEVEL_01). Rewriting the `01` of the LEVEL_01
entry in RAM while the frontend is resident, then starting a game, loads the
other module, and the module loads its own art WAD. See level_route.py.

Usage:
  python tools/bench/levels.py --size 0x484B00
"""
import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ppsspp_bench import BenchError  # noqa: E402

LEVEL01 = {
    'stem': 'LEVEL_01', 'size': 0x46B900,
    'core': {'vblank': 0x96650, 'delta': 0x151E0, 'loop': 0x2FCFC},
    'core_file': {'vblank': 0x0C06FD09, 'delta': 0x3C043D08, 'loop': 0x2A240002},
    'frame_counter': 0x2AF28C, 'player': 0x337940, 'ammo_base': 0x2AE95C, 'entity_manager': 0x2CA0D0,
    'fixes': None,        # None: fixes.DATA applies as is
}


@lru_cache(maxsize=None)
def _sizes():
    import level_port
    out = {}
    for p in sorted(level_port.BIN.glob('LEVEL_*.PRX')):
        out.setdefault((level_port.Prx(p).extent + 0xFF) & ~0xFF, []).append(p.stem)
    return out


@lru_cache(maxsize=None)
def _ported(stem):
    import level_port
    src, dst = level_port.Prx(level_port.BIN / 'LEVEL_01.PRX'), level_port.Prx(level_port.BIN / f'{stem}.PRX')
    out = level_port.port_level(stem)
    prof = {'stem': stem, 'size': int(out['size'], 16), 'core': {}, 'core_file': {}, 'fixes': {}, 'unported': {}}
    for name, r in out['core'].items():
        if r['rva'] is None:
            raise BenchError(f'{stem}: C1 core site {name} not ported ({r.get("why")})')
        prof['core'][name] = int(r['rva'], 16)
        prof['core_file'][name] = dst.word(prof['core'][name])
    for name, r in out['addresses'].items():
        if r['rva'] is None:
            raise BenchError(f'{stem}: address {name} not ported ({r.get("why")})')
        prof[name] = int(r['rva'], 16)
    import importlib.util
    spec = importlib.util.spec_from_file_location('fixes', HERE.parents[1] / 'tools/runtime/fixes.py')
    fx = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fx)
    for name, r in out['fixes'].items():
        if r['rva'] is None:
            prof['unported'][name] = r.get('why')
        else:
            _rva, orig, new = fx.DATA[name]
            prof['fixes'][name] = (int(r['rva'], 16), orig, new)
    del src
    return prof


def profile_for_size(size):
    if size == LEVEL01['size']:
        return LEVEL01
    stems = _sizes().get(size)
    if not stems:
        raise BenchError(f'no level PRX with rcp1 size 0x{size:X}')
    # LEVEL_15 and LEVEL_21 share a size and differ by 14 data bytes; accept a
    # shared size only when every candidate ports to the same profile
    profs = [_ported(s) for s in stems]
    same = [{k: v for k, v in p.items() if k != 'stem'} for p in profs]
    if any(s != same[0] for s in same[1:]):
        raise BenchError(f'rcp1 size 0x{size:X} is shared by {", ".join(stems)} with different ports')
    return profs[0] if len(stems) == 1 else {**profs[0], 'stem': '/'.join(stems)}


def profile(d):
    """(module base, profile) of the resident level."""
    mod = d.module('rcp1')
    return mod['address'], profile_for_size(mod['size'])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--size', required=True)
    a = ap.parse_args()
    p = dict(profile_for_size(int(a.size, 0)))
    fixes = p.pop('fixes')
    unported = p.pop('unported', {})
    print(json.dumps({k: (hex(v) if isinstance(v, int) else v) for k, v in p.items()}, default=str, indent=1))
    print(f'fixes ported: {"all" if fixes is None else len(fixes)}; not ported: {len(unported)}')


if __name__ == '__main__':
    main()
