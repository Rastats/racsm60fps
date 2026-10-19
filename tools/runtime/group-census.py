#!/usr/bin/env python3
"""Read-only census of LEVEL_01 pump-1 groups: callback RVA, class name, active counts.

Manager pointer at module+0x2CA0D0; groups at manager+0x34 (count +0x38), stride 0x50;
group +0x1C callback, +0x0C entity array, +0x3C capacity, +0x4C/+0x4E u16 counts
(summed by the pump). Usage: python tools/runtime/group-census.py --out <file.json>
"""
import argparse, csv, importlib.util, json, struct, time
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('pump_gate', REPO/'tools/runtime/pump-gate.py')
pg = importlib.util.module_from_spec(spec); spec.loader.exec_module(pg)

def names():
    out = {}
    atlas = REPO/'research/v2/c1-residual-timing-atlas/c1-residual-timing-atlas.csv'
    if not atlas.exists():  # local research branch only: census still runs, classes print as '?'
        return out
    for r in csv.DictReader(atlas.open(encoding='utf-8-sig')):
        for it in r['update_functions'].split(';'):
            if it.startswith('M01:'): out[int(it[4:], 16)] = r['class_name']
    return out

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--out', type=Path, required=True); ap.add_argument('--port', type=int, default=60907)
    a = ap.parse_args(); cls = names()
    c = pg.Client('127.0.0.1', a.port); c.connect()
    try:
        base = [m for m in c.request('hle.module.list')['modules'] if m['name'] == 'rcp1' and m.get('isActive')][0]['address']
        mgr = c.read(base+0x2CA0D0, 1)[0]
        arr, n = c.read(mgr+0x34, 2)
        groups = []
        for i in range(n):
            g = c.read(arr+i*0x50, 20)
            cb = g[7]; active = (g[19] & 0xFFFF) + (g[19] >> 16)
            rva = cb-base if base <= cb < base+pg.MODULE_SIZE else None
            groups.append({'i': i, 'callback': hex(rva) if rva is not None else hex(cb),
                           'class': cls.get(rva, '?'), 'active': active, 'capacity': g[15]})
    finally:
        c.close()
    rec = {'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'base': hex(base), 'groups': groups}
    a.out.parent.mkdir(parents=True, exist_ok=True); a.out.write_text(json.dumps(rec, indent=1))
    print(json.dumps([(g['i'], g['class'], g['active']) for g in groups if g['active']]))

if __name__ == '__main__':
    main()
