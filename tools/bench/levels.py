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
                          sites ported with an identical original word only,
                          plus the level's own candidates (NATIVE below)
  native                  {group: [names in fixes]} of those candidates

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

# Candidate fixes read in one level's own code, not ported from LEVEL_01:
# level -> {group: [(rva, original word, fixed word)]}. Each word joins the
# profile's `fixes` as `<group>@<rva>`, and `native` maps the group to them, so
# `C1+tapwin` works like a fixes.py alias. Static reading of LEVEL_22.PRX, 2026-10-23.
NATIVE = {
    'LEVEL_22': {
        # D-pad up / down double-tap (0x1056E8, once per frame from GO): counter 0x240658 +1 per call
        # (0x1057F4); a second press counts when the gap is > 5 and < 30 calls (`addiu a2,a0,-5` and
        # `addiu a2,a0,-0x1E`, once per button). 10 and 60 restore the A0 window in seconds at 60 calls/s.
        'tapwin': [(0x10574C, 0x2486FFFB, 0x2486FFF6), (0x105758, 0x2486FFE2, 0x2486FFC4),
                   (0x1057B8, 0x2486FFFB, 0x2486FFF6), (0x1057C4, 0x2486FFE2, 0x2486FFC4)],
        # Race countdown 0x22DDCC, -1 per frame (0x95988), is set from sixtieths / 60 x 30.0
        # (`lui a0,0x41F0` at 0x95598, store 0x955B0): x 60.0, as in the frames30 family.
        'racecount': [(0x95598, 0x3C0441F0, 0x3C044270)],
        # Player timers +0xA00/+0xA08/+0xA0C/+0xA14/+0xA18 -= f12 (0x28B34, writer 0x28B58 for +0xA08),
        # called at 0x30018 in the substep body 0x2FE6C with the substep delta: twice per frame with
        # 1/30 in A0, once with 1/60 in C1. Delay slot `mov.s f12,f20` -> `add.s f12,f20,f20` (2 x delta),
        # for this call only; `substepdt` doubles the delta of the whole body.
        'boardtimers': [(0x3001C, 0x4600A306, 0x4614A300)],
        # Race AI move 0x10B4D0 (callback group 0x108CA8, entities 0-2), once per frame: velocity
        # entity+0x58 -> +0..8 is in units per frame (cap +0x2C, A0 constants in 1/30 steps) and the
        # sweep 0x10C058 adds all of it to the position (step / |v|, |v| in f20). f20 = 2|v| with the
        # distance left still |v| adds v / 2 per frame, the A0 distance per second. Accelerations unchanged.
        'aimove': [(0x10C034, 0x46000506, 0x46000500), (0x10C048, 0xE7B4007C, 0xE7A0007C)],
        # With aimove, the rest of 0x10B4D0 that acts once per frame on the velocity or heading, so that
        # velocity stays in A0 units per 1/30 s. Data words read only there (checked): yaw-rate target gain
        # and clamp 0.611 (heading turned per frame by s2+0x40) /2; throttle-spring target 0.0889 /2 (the
        # race target; the mode-0 target 0x2409BC 0.0667 has another reader 0xF6A6C and its load 0x109240
        # is relocated, so it is left); lateral damping 0.02 / 0.04 and normal damping 0.1 -> 1 - sqrt(1 - k);
        # vertical step 0.00922 /2. The two springs 0xDD28 / 0xDB90 still run per frame (k, d not refitted).
        # Race time: the player race object (*(entity+0x58)) +0x9C counts frames from GO (+1 at 0x10672C).
        # At the finish (two copies, 0x106758 and 0x106854) it is compared with the saved best (0xE0380)
        # and stored (0xE086C); the Best Times menu shows it x 1/30 (0xB219C) as "%2d : %02d". Here the
        # counter is halved before the compare and the store (A0 units, so saves stay A0-compatible and
        # the menu reads right), using the two nop delay slots of each block. The award check at 0x106B08
        # (timer <= 6150.0 frames, 205 s at 30/s, data read only there) gets 12300.0.
        'racetime': [(0x10676C, 0x00000000, 0x922500B1), (0x106770, 0x8E25009C, 0x8E26009C),
                     (0x106774, 0x00A4202B, 0x00063042), (0x106778, 0x10800005, 0x00C4202B),
                     (0x10677C, 0x00000000, 0x10800004), (0x106784, 0x922500B1, 0x00042042),
                     (0x106868, 0x00000000, 0x922500B1), (0x10686C, 0x8E25009C, 0x8E26009C),
                     (0x106870, 0x00A4202B, 0x00063042), (0x106874, 0x10800005, 0x00C4202B),
                     (0x106878, 0x00000000, 0x10800004), (0x106880, 0x922500B1, 0x00042042),
                     (0x24061C, 0x45C03000, 0x46403000)],
        # Board speed spring 0xDAC4 (v = k(T - x) - 0.2 v, x += v; x = player+0x230, once per substep, no
        # delta). Its target block 0x4A190 brakes (T = 0.3 t, or t - 0.2333) or accelerates (T = t + 0.2667)
        # with k = 0.1 when 0x476D8 sees the event G+0x159, set once per frame by the speed/slow volume
        # entities (0xF14E0 / 0xF14F0) and cleared by the substep that uses it: in A0 one substep of two
        # brakes, in C1 every one, so the climb floor is T = 0.1 (HUD 3.00) against an A0 cycle mean of
        # 0.137 (HUD 4.1). Data words read only there (checked): k 0x222324 (0x4A3A0, 0x4A440), brake
        # term 0x22231C (0x4A410, 0x4A430), accelerate term 0x222318 (0x4A390), refitted so one C1 substep
        # has the A0 cycle's steady state and first-second distance (springsim.py, 2026-11-08: steady
        # state equal, distance over 1 s within 0.1 %). The same words also serve ground surface types 3/5
        # (G+0x158, per substep, already right in C1): a course with such ground would drift from A0 there.
        'slope': [(0x222324, 0x3DCCCCCD, 0x3D8068DC), (0x22231C, 0xBE6EEEF0, 0xBE48CE3A),
                  (0x222318, 0x3E888889, 0x3E657DEA)],
        'aiphys': [(0x2409D8, 0x3F1C61AB, 0x3E9C61AB), (0x2409B8, 0x3DB60B62, 0x3D360B62),
                   (0x2409C0, 0x3CA3D70A, 0x3C24AAE1),
                   (0x2409C4, 0x3D23D70A, 0x3CA58313), (0x240AB8, 0x3DCCCCCD, 0x3D523176),
                   (0x240A00, 0x3C1718CF, 0x3B9718CF)],
    },
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
    prof['native'] = {}
    for group, words in NATIVE.get(stem, {}).items():
        for rva, orig, new in words:
            if dst.word(rva) != orig:
                raise BenchError(f'{stem}: native fix {group} expects 0x{orig:08X} at +0x{rva:X}, '
                                 f'the PRX holds 0x{dst.word(rva):08X}')
            prof['fixes'][f'{group}@{rva:#x}'] = (rva, orig, new)
        prof['native'][group] = [f'{group}@{rva:#x}' for rva, _, _ in words]
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
