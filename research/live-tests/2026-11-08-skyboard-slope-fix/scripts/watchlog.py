"""Store events of a rec.py --watch / --watch-player run, grouped by PC.
python watchlog.py RUN [--list N] [--pc RVA]   (run dir under work/runs)
"""
import argparse, collections, json, os

R = os.environ.get('RACSM_ROOT', 'D:/sandboxes/racsm60fps') + '/work/runs/'
ap = argparse.ArgumentParser()
ap.add_argument('run')
ap.add_argument('--list', type=int, default=40, help='events printed in order')
ap.add_argument('--pc', default='', help='only this PC (hex RVA)')
ap.add_argument('--every', type=int, default=0, help='with --pc: print one event per N vblanks (time series)')
a = ap.parse_args()
m = json.load(open(R + a.run + '/samples.json'))
s, ev = m['samples'], m['events']
print(f'{a.run} ({m["config"]}): {len(s)} samples, v {s[0]["v"] if s else None}..{s[-1]["v"] if s else None}')
w = [e for e in ev if 'watch' in e and (not a.pc or e['pc'] == a.pc)]
print(f'{len(w)} store events; other events: {[e for e in ev if "watch" not in e][:8]}')
by = collections.Counter((e['watch'], e['pc'], e['ra']) for e in w)
for (wa, pc, ra), n in by.most_common():
    vals = [e['newf'] for e in w if (e['watch'], e['pc'], e['ra']) == (wa, pc, ra)]
    print(f'  {wa} pc {pc} ra {ra}: {n} stores, new {min(vals):.4f}..{max(vals):.4f}')
if a.every:
    pos = {x['v']: x for x in s}
    last = None
    for e in w:
        if e['v'] is not None and (last is None or e['v'] - last >= a.every):
            last = e['v']
            x = pos.get(e['v'], {})
            print(f'  v{e["v"]:5d} {e["oldf"]:9.5f} -> {e["newf"]:9.5f}  pos {x.get("pos")} hud {x.get("hud", 0):.2f}')
for e in w[:a.list]:
    extra = {k: v for k, v in e.items() if k.startswith('f') and k[1:].isdigit()}
    print(f'  v{e["v"]} {e["watch"]} pc {e["pc"]} ra {e["ra"]} {e["oldf"]:.5f} -> {e["newf"]:.5f} {extra}')
for x in s[:: max(1, len(s) // 12)]:
    print(f'  v{x["v"]} pos {x["pos"]} hud {x["hud"]:.2f}')
