"""60 Hz values for the LEVEL_22 AI per-frame constants; 1/30 words reachable from lui 0x24."""
import math, struct, sys
sys.path.insert(0, 'D:/sandboxes/racsm60fps/wt-banc/tools/bench')
import level_port
prx = level_port.Prx(level_port.BIN / 'LEVEL_22.PRX')
f2w = lambda f: struct.unpack('<I', struct.pack('<f', f))[0]
w2f = lambda w: struct.unpack('<f', struct.pack('<I', w))[0]


def spring(k, d):
    # substep: v' = (1-d) v - k e ; e' = e + v'. Per call two substeps. Half the call period:
    # eigenvalues sqrt(lambda): det' = sqrt(det), tr' = sqrt(tr + 2 sqrt(det)).
    det, tr = 1 - d, 2 - k - d
    d2 = 1 - math.sqrt(det)
    tr2 = math.sqrt(tr + 2 * math.sqrt(det))
    return 2 - d2 - tr2, d2


for name, k, d in (('accel', w2f(0x3D4CCCCD), w2f(0x3E4CCCCD)), ('steer', w2f(0x3D23D70A), w2f(0x3E4CCCCD))):
    k2, d2 = spring(k, d)
    print(name, k, d, '->', k2, hex(f2w(k2)), d2, hex(f2w(d2)))
for name, rva, kind in (('yawgain', 0x2409D8, 'half'), ('acc0889', 0x2409B8, 'half'), ('lat02', 0x2409C0, 'damp'),
                        ('lat04', 0x2409C4, 'damp'), ('norm01', 0x240AB8, 'damp'), ('grav', 0x240A00, 'half')):
    w = prx.word(rva)
    f = w2f(w)
    g = f / 2 if kind == 'half' else 1 - math.sqrt(1 - f)
    print(name, hex(rva), hex(w), f, '->', g, hex(f2w(g)), w2f(f2w(g)))
third = [a for a in range(0x238000, min(0x248000, 4 * len(prx.words)), 4) if prx.word(a) == 0x3D088889]
print('1/30 words:', [hex(a) for a in third[:12]])
