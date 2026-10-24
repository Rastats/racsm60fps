"""Static: every `addiu rX, rY, -0x4518` (the award status block, lui 9 before relocation) in LEVEL_22.PRX,
with the next store or load through that register.
python blockrefs.py
"""
import struct, sys
import capstone
sys.path.insert(0, 'D:/sandboxes/racsm60fps/wt-banc/tools/bench')
import level_port  # noqa

prx = level_port.Prx(level_port.BIN / 'LEVEL_22.PRX')
md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS32 | capstone.CS_MODE_LITTLE_ENDIAN)


def ins(a):
    w = prx.word(a)
    d = list(md.disasm(struct.pack('<I', w), a))
    return w, (f'{d[0].mnemonic} {d[0].op_str}' if d else '?')


a, end = prx.text[0], prx.text[1]
while a < end:
    try:
        w = prx.word(a)
    except Exception:
        break
    if w >> 26 == 0x09 and w & 0xFFFF == 0xBAE8:
        rt = (w >> 16) & 31
        for k in range(1, 6):          # first memory access through rt
            w2, t = ins(a + 4 * k)
            op = w2 >> 26
            if op in (0x20, 0x24, 0x28, 0x23, 0x2B, 0x21, 0x25, 0x29) and (w2 >> 21) & 31 == rt:
                print(f'{a:#08x}  {a + 4 * k:#08x}: {t}')
                break
    a += 4
