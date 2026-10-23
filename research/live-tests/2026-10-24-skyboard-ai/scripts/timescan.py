"""After a LEVEL_22 win (menu shown), find RAM words holding the race time: timescan.py FRAMES OUT.json

Scans user RAM 0x08800000-0x0A000000 for u32 FRAMES-2..FRAMES+2 and for floats within 0.5 of
FRAMES / 30 and FRAMES / 60, and reports each hit with its module RVA when inside rcp1.
"""
import json, struct, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, 'D:/sandboxes/racsm60fps/wt-banc/tools/bench')
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa
import levels  # noqa

frames, out = int(sys.argv[1]), Path(sys.argv[2])
hits = []
with Debugger(DEFAULT_PORT).connect() as d:
    base, prof = levels.profile(d)
    size = d.module('rcp1')['size']
    d.pause()
    try:
        for start in range(0x08800000, 0x0A000000, 0x40000):
            try:
                buf = d.read(start, 0x40000)
            except Exception:
                continue
            u = np.frombuffer(buf, dtype='<u4')
            f = np.frombuffer(buf, dtype='<f4')
            for k in np.nonzero((u >= frames - 2) & (u <= frames + 2))[0]:
                hits.append(('u32', start + 4 * int(k), int(u[k])))
            with np.errstate(invalid='ignore'):
                for tgt in (frames / 30, frames / 60, frames / 59.94):
                    for k in np.nonzero(np.abs(f - tgt) < 0.5)[0]:
                        hits.append(('f32', start + 4 * int(k), float(f[k])))
    finally:
        d.resume()
rows = [{'kind': k, 'addr': hex(a), 'rva': hex(a - base) if base <= a < base + size else None, 'value': v}
        for k, a, v in hits]
out.write_text(json.dumps({'frames': frames, 'base': hex(base), 'hits': rows}, indent=1))
for r in rows:
    print(r)
