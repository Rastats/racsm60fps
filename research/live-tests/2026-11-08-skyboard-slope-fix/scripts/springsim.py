"""Board speed spring 0xDAC4 under a brake/accelerate volume: A0 (2 substeps per frame, the volume
event consumed by the first) against C1 (1 substep per frame, the event every substep), with the
original and the `slope` data words. Prints the float32 hex of the new words and the response.
python springsim.py [--d 0.2] [--vmax 1.0]

Spring (disassembly 0xDAC4..0xDB24): v = k*(T - x) - d*v; v clamped to +-vmax; x += v.
Targets (0x4A190..0x4A4C8): normal t; accelerate t + A (0x222318); brake t*(1 - B/(1/3)) if
t >= 1/3 else t - B (B = -0x22231C); k = K (0x222324) on a volume substep, 0.02 otherwise.
"""
import argparse, struct

ap = argparse.ArgumentParser()
ap.add_argument('--d', type=float, default=0.2)
ap.add_argument('--vmax', type=float, default=1.0)
a = ap.parse_args()
F13 = struct.unpack('<f', struct.pack('<f', 1 / 3))[0]


def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


def hexf(x):
    return '0x%08X' % struct.unpack('<I', struct.pack('<f', x))[0]


def target(kind, t, A, B):
    if kind == 'acc':
        return t + A
    if kind == 'brk':
        return t + (-B * t) / F13 if t >= F13 else t - B
    return t


def run(pattern, kind, t, K, A, B, x0, n=240):
    """pattern: per-substep True when the volume event applies. Returns x after each substep."""
    x, v, out = x0, 0.0, []
    for i in range(n):
        ev = pattern(i)
        T = target(kind, t, A, B) if ev else t
        k = K if ev else 0.02
        T = min(max(T, 0.0), 0.8)
        v = f32(k * (T - x) - a.d * v)
        v = max(-a.vmax, min(a.vmax, v))
        x = f32(x + v)
        out.append(x)
    return out


def word(u):
    return struct.unpack('<f', struct.pack('<I', u))[0]


# the PRX words (prxdis.py --f32 0x222318 4): A 0x3E888889, -B 0xBE6EEEF0, K 0x3DCCCCCD
ORIG = dict(K=word(0x3DCCCCCD), A=word(0x3E888889), B=-word(0xBE6EEEF0))
a0 = lambda i: i % 2 == 0          # A0: first substep of each frame (60 substeps/s)
c1 = lambda i: True                # C1: every substep


def a0_mean(kind, t):
    """A0 steady state: mean speed over the 2-substep cycle (the distance per second / 60)."""
    s = run(a0, kind, t, x0=t, n=2000, **ORIG)
    return (s[-1] + s[-2]) / 2


# C1 settles on its target, so B and A make the target equal the A0 cycle mean (linear in t:
# checked on both brake branches below); K is then fitted on the distance in the first second
B = F13 - a0_mean('brk', F13)
A = a0_mean('acc', F13) - F13


def err(K):
    e = 0.0
    for kind, t in (('brk', F13), ('brk', 0.25), ('acc', F13)):
        for x0 in (t, 0.26, 0.45):        # 0.26: the measured climb entry (HUD 7.75)
            e += (sum(run(a0, kind, t, x0=x0, n=60, **ORIG)) - sum(run(c1, kind, t, x0=x0, n=60, K=K, A=A, B=B))) ** 2
    return e


K = min((0.04 + i * 0.0001 for i in range(401)), key=err)
NEW = dict(K=f32(K), A=f32(A), B=f32(B))
print(f'fitted: B {B:.6f} (weighted mean 0.194444)  A {A:.6f} (0.222222)  K {K:.4f} (0.06)')
print(f'brake else-branch check: A0 mean t=0.25 -> B {0.25 - a0_mean("brk", 0.25):.6f}')
print('slope words: 0x222324 K', hexf(NEW['K']), ' 0x222318 A', hexf(NEW['A']), ' 0x22231C -B', hexf(-NEW['B']))
print('orig  words: K', hexf(0.1), ' A', hexf(0.26666668), ' -B', hexf(-0.23333333))
for kind, t, x0 in (('brk', F13, F13), ('brk', 0.5, 0.5), ('brk', 0.25, 0.25),
                    ('acc', F13, F13), ('acc', 0.5, 0.5)):
    A = run(a0, kind, t, x0=x0, **ORIG)
    C = run(c1, kind, t, x0=x0, **ORIG)
    N = run(c1, kind, t, x0=x0, **NEW)
    pair = lambda s, i: (s[i] + s[i + 1]) / 2 if i + 1 < len(s) else s[i]
    print(f'\n{kind} t={t:.4f} x0={x0:.4f}   HUD = 30*x (frame mean)   substeps 0.25 s / 0.5 s / 1 s / 4 s')
    for name, s in (('A0', A), ('C1', C), ('C1+slope', N)):
        print(f'  {name:9s}', ' '.join(f'{30 * pair(s, i):6.3f}' for i in (14, 30, 60, 238)))
    # distance covered (sum of speeds) over the first second, the climb-time proxy
    print('  dist 1 s  A0 %.3f  C1 %.3f  C1+slope %.3f' % (sum(A[:60]), sum(C[:60]), sum(N[:60])))
# a one-frame tap (event on 1 frame only): A0 one volume substep, C1 one volume substep
for kind in ('brk', 'acc'):
    tap = lambda i: i == 0
    s0 = sum(run(tap, kind, F13, x0=F13, **ORIG)[:120])
    s1 = sum(run(tap, kind, F13, x0=F13, **NEW)[:120])
    print(f'\none-frame {kind} volume: distance over 2 s  A0 {s0:.4f}  C1+slope {s1:.4f}')
# brake ground (surface type 3, G+0x158 = 2): every substep in both configs, measured 9-10 vblanks
# per lap on LEVEL_22 (surfaces.py): what the shared words cost there
for n_ground in (10,):
    g = lambda i: i < n_ground
    for x0 in (0.26, 0.4):
        s0 = sum(run(g, 'brk', F13, x0=x0, n=180, **ORIG))
        s1 = sum(run(g, 'brk', F13, x0=x0, n=180, **NEW))
        print(f'brake ground {n_ground} substeps, entry HUD {30 * x0:.1f}: distance over 3 s  A0/C1 {s0:.3f}'
              f'  C1+slope {s1:.3f}  ({s1 - s0:+.3f} u, {(s1 - s0) / (30 * F13 / 30 * 60) * 60:+.3f} vblanks at t)')
