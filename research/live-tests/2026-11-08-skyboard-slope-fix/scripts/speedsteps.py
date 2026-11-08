"""Per-store change of the board speed player+0x230 between two vblanks, by writer PC.
python speedsteps.py RUN V0 V1   (run dir under work/runs, rec.py --watch-player 230 ...)
Prints, for each store in [V0, V1]: vblank, PC, old -> new, delta, and the registers logged.
"""
import json, os, sys

R = os.environ.get('RACSM_ROOT', 'D:/sandboxes/racsm60fps') + '/work/runs/'
run, v0, v1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
m = json.load(open(R + run + '/samples.json'))
watch = None
for e in m['events']:
    if 'watch' not in e or e['v'] is None or not v0 <= e['v'] <= v1:
        continue
    if watch is None:
        base = int(e['watch'], 16)
    if e['pc'] not in ('0xdb20', '0x4903c', '0xdadc', '0x4a438', '0x4a22c', '0x4a260'):
        continue
    regs = ' '.join(f'{k}={v:.5f}' for k, v in e.items() if k.startswith('f') and k[1:].isdigit())
    print(f'v{e["v"]:5d} {e["watch"]} {e["pc"]:>8} {e["oldf"]:9.5f} -> {e["newf"]:9.5f} d {e["newf"] - e["oldf"]:+.5f}  {regs}')
