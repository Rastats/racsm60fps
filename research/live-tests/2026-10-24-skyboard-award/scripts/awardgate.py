"""LEVEL_22 race-end award gate (0x106A44-0x106B60): the relocated status block and its bytes.

At the finish, with player race object +0xAF and +0xB0 both nonzero:
  status +0xE in 1..0x3F -> award 0x78 (0x1CE34), +0xE := 0x40, skip the time check;
  else status +0xC in 1..0x3F -> race counter +0x9C <= float 0x24061C ? award 0x79, +0xC := 0x40 : +0xC := 0x80.
The block address is built by `lui/addiu` at 0x106A5C/0x106A60, relocated at load, so it is read from RAM.

python awardgate.py [--state NAME ...] [--set-c N] [--set-e N] [--set-thr F]
--set-c / --set-e / --set-thr are TEST AIDS (RAM only): they write the status byte or the threshold after the load.
"""
import argparse, json, struct, sys, time
sys.path.insert(0, 'D:/sandboxes/racsm60fps/wt-banc/tools/bench')
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa
import levels, states  # noqa
sys.path.insert(0, 'D:/sandboxes/racsm60fps/wt-banc/research/live-tests/2026-10-24-skyboard-ai/scripts')
import bestrec  # noqa


def block(d, base):
    hi, lo = d.u32(base + 0x106A5C), d.u32(base + 0x106A60)
    assert hi >> 16 == 0x3C04 and lo >> 16 == 0x2484, (hex(hi), hex(lo))
    off = lo & 0xFFFF
    return ((hi & 0xFFFF) << 16) + (off - 0x10000 if off & 0x8000 else off)


def snap(d):
    base, prof = levels.profile(d)
    b = block(d, base)
    raw = d.read(b, 0x10)
    thr = d.f32(base + 0x24061C)
    save = d.u32(base + 0x220A60)
    sv = d.read(save + 0x880, 0x80)
    # 0xDFEF0(-1, 0xff): level word 0x23D7A8 in {3, 0x16} -> 0x1B0 + idx; in {6, 0x17} -> 0x1B8 + 2 idx;
    # idx = (save 0x880+0x4B & 0xF) % 6 (0xDFB0C). +0xC is armed only for 0x1BE (0x106628).
    return {'block': hex(b), 'blockRva': hex(b - base), 'bytes': raw.hex(' '), 'c': raw[0xC], 'e': raw[0xE],
            'level': d.u32(base + 0x23D7A8), 'challengeIdx': (sv[0x4B] & 0xF) % 6,
            'award78': sv[0x78], 'award79': sv[0x79],      # 0x1CE34(id, 1, bit): bit 2 of 0x8F8, bit 4 of 0x8F9
            'threshold': thr, 'records': [(r['name'], r['frames'], r['shown']) for r in bestrec.read(d)]}


ap = argparse.ArgumentParser()
ap.add_argument('--state', nargs='*', default=[])
ap.add_argument('--set-c', type=int)
ap.add_argument('--set-e', type=int)
ap.add_argument('--set-thr', type=float, help='TEST AID: overwrite the float threshold 0x24061C')
a = ap.parse_args()
out = {}
for name in a.state or ['-']:
    if name != '-':
        states.load(name)
        time.sleep(1.5)
    with Debugger(DEFAULT_PORT).connect() as d:
        s = snap(d)
        if a.set_c is not None or a.set_e is not None:
            b = int(s['block'], 16)
            w = bytearray(d.read(b + 0xC, 4))       # +0xC..+0xF: one aligned word
            if a.set_c is not None:
                w[0] = a.set_c
            if a.set_e is not None:
                w[2] = a.set_e
            d.write_u32(b + 0xC, int.from_bytes(w, 'little'))
            s['after'] = snap(d)
        if a.set_thr is not None:
            base, _ = levels.profile(d)
            d.write_u32(base + 0x24061C, struct.unpack('<I', struct.pack('<f', a.set_thr))[0])
            s['after'] = snap(d)
    out[name] = s
print(json.dumps(out, indent=1))
