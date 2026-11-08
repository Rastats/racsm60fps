"""Readers of LEVEL_22 data words addressed as lui r,HI / op x,LO(r): refs.py 0x2409b8 [...]"""
import sys
sys.path.insert(0, 'D:/sandboxes/racsm60fps/wt-slope/tools/bench')
import level_port
prx = level_port.Prx(level_port.BIN / 'LEVEL_22.PRX')
lo, hi = prx.text
W = [prx.word(a) for a in range(0, hi, 4)]
for t in (int(x, 0) for x in sys.argv[1:]):
    hi16 = (t + 0x8000) >> 16
    lo16 = t & 0xFFFF
    hits = []
    for a in range(lo, hi, 4):
        w = W[a // 4]
        op = w >> 26
        if op in (0x23, 0x31, 0x09) and (w & 0xFFFF) == lo16:   # lw, lwc1, addiu
            rs = (w >> 21) & 31
            for k in range(1, 40):
                p = W[(a - 4 * k) // 4]
                if p >> 26 == 0x0F and ((p >> 16) & 31) == rs:
                    if p & 0xFFFF == hi16:
                        hits.append(hex(a) + ('' if op != 0x09 else '(addr)'))
                    break
    print(hex(t), len(hits), ' '.join(hits))
