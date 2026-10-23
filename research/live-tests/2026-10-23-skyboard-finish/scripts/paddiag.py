"""Why the D-pad never reaches the LEVEL_22 double-tap detector (0x1056E8).

0x1056E8 reads its pad word through 0x68260(0x10): that returns pad struct +0x30 (0x90F38) only if
0x68360(0x10) is true, i.e. 0x10 & (mask | 1) != 0, mask = the word loaded at 0x68364 (relocated).
This script resolves the mask address from the relocated lui/lw pair, then, from GO + 3 s, reads the
mask and the pad struct each frame while the debugger holds each D-pad direction in turn.

Known flaw: `pad` (base+0x90F08) is MIPS code, not the pad struct; only `mask` is meaningful.

python paddiag.py --state banc-skyboard-arrive --config A0 --out FILE.json
"""
import argparse, json, struct, sys, time
from pathlib import Path
BENCH = Path('D:/sandboxes/racsm60fps/wt-banc/tools/bench')
sys.path.insert(0, str(BENCH))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa
from breakloop import BreakLoop  # noqa
import states, wordfix, levels  # noqa

ap = argparse.ArgumentParser()
ap.add_argument('--state', required=True)
ap.add_argument('--config', default='A0')
ap.add_argument('--out', type=Path, required=True)
a = ap.parse_args()
PLAN = [('none', 20), ('up', 20), ('none', 20), ('down', 20), ('none', 20), ('left', 20), ('right', 20),
        ('none', 20)]
if a.state != '-':
    states.load(a.state)
    time.sleep(1.0)
with Debugger(DEFAULT_PORT).connect() as d:
    d.release_all()
    core, *fx = a.config.split('+')
    wordfix.apply(d, core, set(fx))
    base, prof = levels.profile(d)
    lui, lw = d.u32(base + 0x68360), d.u32(base + 0x68364)
    hi = (lui & 0xFFFF) << 16
    lo = lw & 0xFFFF
    mask_addr = (hi + (lo - 0x10000 if lo & 0x8000 else lo)) & 0xFFFFFFFF
    pad = base + 0x90F08
    info = {'base': hex(base), 'lui': hex(lui), 'lw': hex(lw), 'mask_addr': hex(mask_addr)}
    print(info)
    rows, plan, start = [], list(PLAN), []

    def on_frame(t, value):
        if value is None:
            return
        rf = struct.unpack('<i', d.read(base + 0x240658, 4))[0]
        if rf < 90:
            return
        if not start:
            start.append(0)
        words = struct.unpack('<16I', d.read(pad, 64))
        row = {'rf': rf, 'mask': hex(d.u32(mask_addr)), 'held': plan[0][0],
               'pad': {f'+{4 * k:02x}': hex(w) for k, w in enumerate(words) if w},
               'state64C': d.u32(base + 0x24064C)}
        rows.append(row)
        name, n = plan[0]
        if start[0] == 0:
            d.buttons(**{b: b == name for b in ('up', 'down', 'left', 'right')})
        start[0] += 1
        if start[0] >= n:
            plan.pop(0)
            start[0] = 0
        return not plan

    loop = BreakLoop(d, base)
    loop.every_frame(on_frame)
    loop.at_end(lambda: d.release_all())
    loop.run(30, wall_limit=200)
a.out.write_text(json.dumps({'info': info, 'rows': rows}, indent=0) + '\n')
for r in rows[::4]:
    print(r)
