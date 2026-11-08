"""Disassemble LEVEL_22.PRX: prxdis.py (not dis.py: that name shadows the stdlib module capstone imports) <rva> <count> [--find-jal RVA] [--find-word HEX]"""
import sys, struct
from pathlib import Path
import capstone
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[4] / 'tools/bench'))
import level_port

prx = level_port.Prx(level_port.BIN / 'LEVEL_22.PRX')
md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS32 | capstone.CS_MODE_LITTLE_ENDIAN)

def dis(start, n):
    for i in range(n):
        a = start + 4 * i
        w = prx.word(a)
        ins = list(md.disasm(struct.pack('<I', w), a))
        txt = f'{ins[0].mnemonic} {ins[0].op_str}' if ins else '?'
        if w >> 26 == 3 or w >> 26 == 2:
            txt += f'   ; -> {(w & 0x3FFFFFF) << 2:#x}'
        print(f'{a:#08x}: {w:08x}  {txt}')

args = sys.argv[1:]
if args[0] == '--find-jal':
    t = int(args[1], 0)
    lo, hi = prx.text
    for a in range(lo, hi, 4):
        w = prx.word(a)
        if w >> 26 in (2, 3) and (w & 0x3FFFFFF) << 2 == t:
            print(hex(a))
elif args[0] == '--find-word':
    t = int(args[1], 16)
    m = int(args[2], 16) if len(args) > 2 else 0xFFFFFFFF
    lo, hi = prx.text
    for a in range(lo, hi, 4):
        if prx.word(a) & m == t:
            print(hex(a))
elif args[0] == '--f32':
    a = int(args[1], 0)
    for i in range(int(args[2]) if len(args) > 2 else 1):
        w = prx.word(a + 4 * i)
        print(f'{a + 4 * i:#x}: {w:08x} {struct.unpack("<f", struct.pack("<I", w))[0]}')
else:
    dis(int(args[0], 0), int(args[1]))
