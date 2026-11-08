"""Write watch on the LEVEL_22 award status word (block +0xC..+0xF), armed right after a state load.

Every store that changes the word stops the CPU: logs the emulated tick, PC and ra (RVAs), the pending
store, a0-a3/s0-s3/v0/v1, 16 stack words, raceFrames (0x240658) and the block bytes. No autopilot:
optional held buttons (--hold square) and stick (--stick x y) from the first frame.
The CPU is left paused at the end, so the instance does not keep running unobserved.

python watch78.py --state banc-skyboard-arrive --seconds 40 [--hold square] [--config C1+...] --out <run>
"""
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, 'D:/sandboxes/racsm60fps/wt-award/tools/bench')
from ppsspp_bench import Debugger, DEFAULT_PORT, DEFAULT_ROOT  # noqa
from breakloop import pending_store, CPU_HZ  # noqa
import levels, states, wordfix  # noqa

REGS = {'v0': 2, 'v1': 3, 'a0': 4, 'a1': 5, 'a2': 6, 'a3': 7, 's0': 16, 's1': 17, 's2': 18, 's3': 19, 'sp': 29, 'ra': 31}

ap = argparse.ArgumentParser()
ap.add_argument('--state', required=True)
ap.add_argument('--config', default='A0')
ap.add_argument('--seconds', type=float, default=40.0, help='emulated seconds after the watch is armed')
ap.add_argument('--hold', nargs='*', default=[], help='buttons held from the first frame (e.g. square)')
ap.add_argument('--stick', nargs=2, type=float, default=None)
ap.add_argument('--out', required=True)
a = ap.parse_args()

states.load(a.state)
ev_log = []
with Debugger(DEFAULT_PORT).connect() as d:
    if d.cpu().get('stepping'):          # left paused by an earlier run: wordfix pauses itself
        d.resume()
    core, *fx = a.config.split('+')
    applied = wordfix.apply(d, core, set(fx))
    if not d.cpu().get('stepping'):
        d.pause()
    base, prof = levels.profile(d)
    hi, lo = d.u32(base + 0x106A5C), d.u32(base + 0x106A60)
    blk = ((hi & 0xFFFF) << 16) + ((lo & 0xFFFF) - 0x10000 if lo & 0x8000 else lo & 0xFFFF)
    rf = base + 0x240658
    d.release_all()
    if a.hold:
        d.buttons(**{b: True for b in a.hold})
    if a.stick:
        d.stick(*a.stick)
    t0 = int(d.cpu()['ticks'])
    start = {'tick': t0, 'block': hex(blk), 'bytes': d.read(blk, 0x10).hex(' '), 'raceFrames': d.u32(rf),
             'applied': len(applied['writes'])}
    d.add_mem_breakpoint(blk + 0xC, 4, write=True, change=True)
    d.resume_quiet()
    span = int(a.seconds * CPU_HZ)
    deadline = time.monotonic() + a.seconds * 6 + 60
    try:
        while time.monotonic() < deadline:
            ev = d.wait_event('cpu.stepping', timeout=1.0)
            if ev is None:
                st = d.cpu()
                if int(st['ticks']) - t0 >= span:
                    break
                if not st.get('stepping'):
                    continue
                ev = st
            t, pc = int(ev['ticks']), int(ev['pc'])
            regs = {k: d.call('cpu.getReg', category=0, register=r)['uintValue'] for k, r in REGS.items()}
            ea, size, new = pending_store(d, pc)
            stack = d.u32(regs['sp'], 16)
            rec = {'t': t, 'dt_s': round((t - t0) / CPU_HZ, 4), 'pc': hex(pc - base), 'ra': hex(regs['ra'] - base),
                   'store': [hex(ea - blk), size, hex(new)], 'bytes': d.read(blk, 0x10).hex(' '),
                   'raceFrames': d.u32(rf), 'regs': {k: hex(v) for k, v in regs.items()},
                   'stack': [hex(w - base) if base <= w < base + 0x300000 else hex(w) for w in stack]}
            ev_log.append(rec)
            print(json.dumps({k: rec[k] for k in ('dt_s', 'pc', 'ra', 'store', 'raceFrames')}), flush=True)
            d.resume_quiet()
    finally:
        d.pause()
        d.remove_mem_breakpoint(blk + 0xC, 4)
        d.release_all()
        end = {'tick': int(d.cpu()['ticks']), 'bytes': d.read(blk, 0x10).hex(' '), 'raceFrames': d.u32(rf)}
out = DEFAULT_ROOT / 'work/runs' / a.out
out.mkdir(parents=True, exist_ok=True)
(out / 'watch78.json').write_text(json.dumps({'args': vars(a), 'start': start, 'events': ev_log, 'end': end}, indent=1))
print(json.dumps({'start': start, 'end': end, 'n': len(ev_log)}))
