"""Race with a TEST AID: status +0xC := 1, +0xE := 0 written ~25 s after launch (after GO and race init).
python gaterun.py <config> <out> [rec.py args...]
Logs awardgate snapshots (c, e, award79) before, after the write, every 60 s, and after the race.
"""
import json, os, subprocess, sys, time

os.environ['RACSM_ROOT'] = 'D:/sandboxes/racsm60fps'
S = 'D:/sandboxes/racsm60fps/wt-banc/research/live-tests/2026-10-24-skyboard-award/scripts'
config, out, extra = sys.argv[1], sys.argv[2], sys.argv[3:]
log = open(f'D:/sandboxes/racsm60fps/work/runs/{out}.gate.log', 'w')


def gate(*args):
    r = subprocess.run([sys.executable, f'{S}/awardgate.py', *args], capture_output=True, text=True)
    try:
        s = json.loads(r.stdout)['-']
        s = s.get('after', s)
        line = {k: s[k] for k in ('c', 'e', 'award78', 'award79', 'threshold', 'records')}
    except Exception:
        line = {'err': r.stderr[-400:]}
    line['wall'] = round(time.monotonic() - t0, 1)
    line['args'] = args
    log.write(json.dumps(line) + '\n'); log.flush()


t0 = time.monotonic()
p = subprocess.Popen(['bash', f'{S}/race.sh', 'banc-skyboard-arrive', config, out, *extra])
time.sleep(25)
gate()
gate('--set-c', '1', '--set-e', '0', *(['--set-thr', os.environ['THR']] if os.environ.get('THR') else []))
while p.poll() is None:
    time.sleep(60)
    if p.poll() is None:
        gate()
gate()
log.write(f'race.sh exit {p.returncode}\n')
