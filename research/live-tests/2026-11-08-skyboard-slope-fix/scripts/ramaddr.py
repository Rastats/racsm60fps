"""Resolve a relocated lui/addiu (or lui/lwc1) pair from RAM: absolute address, RVA from the rcp1 base.
python ramaddr.py LUI_RVA LO_RVA [--off HEX] [--n N]   e.g. ramaddr.py 0x4a1a0 0x4a1a4 --off 0x68
Prints the float at address + off (N words).
"""
import argparse, struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tools/bench'))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa
import levels  # noqa

ap = argparse.ArgumentParser()
ap.add_argument('lui', type=lambda s: int(s, 0))
ap.add_argument('lo', type=lambda s: int(s, 0))
ap.add_argument('--off', type=lambda s: int(s, 0), default=0)
ap.add_argument('--n', type=int, default=1)
a = ap.parse_args()
with Debugger(DEFAULT_PORT).connect() as d:
    base, _ = levels.profile(d)
    hi, lo = d.u32(base + a.lui), d.u32(base + a.lo)
    lo16 = lo & 0xFFFF
    addr = ((hi & 0xFFFF) << 16) + (lo16 - 0x10000 if lo16 & 0x8000 else lo16)
    print(f'lui {hi:08x} lo {lo:08x} -> {addr:#x} (rva {addr - base:#x})')
    for i in range(a.n):
        x = addr + a.off + 4 * i
        w = d.u32(x)
        print(f'  {x:#x} (+{a.off + 4 * i:#x}): {w:08x} {struct.unpack("<f", struct.pack("<I", w))[0]}')
