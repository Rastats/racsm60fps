"""Who writes AI 0's position (group 0x108CA8): break on writes to entity+0x30..0x38 after GO.

python aiwriter.py --state banc-skyboard-arrive --config C1 --after 300 --frames 6 --out f.json
"""
import argparse, json, struct, sys, time
from pathlib import Path
BENCH = Path('D:/sandboxes/racsm60fps/wt-banc/tools/bench')
sys.path.insert(0, str(BENCH))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa
from breakloop import BreakLoop, pending_store  # noqa
import states, wordfix, levels, entities  # noqa

ap = argparse.ArgumentParser()
ap.add_argument('--state', required=True)
ap.add_argument('--config', default='C1')
ap.add_argument('--after', type=int, default=300, help='race counter value to reach first')
ap.add_argument('--frames', type=int, default=6)
ap.add_argument('--slot', type=int, default=0)
ap.add_argument('--offs', default='0x30,0x34,0x38')
ap.add_argument('--ptr', type=lambda s: int(s, 0), default=None, help='watch *(entity+PTR)+offs instead')
ap.add_argument('--group',type=lambda s: int(s, 16), default=0x108CA8)
ap.add_argument('--out', type=Path, required=True)
a = ap.parse_args()
states.load(a.state)
time.sleep(1.0)
R = lambda d, cat, r: d.call('cpu.getReg', category=cat, register=r)['uintValue']
with Debugger(DEFAULT_PORT).connect() as d:
    d.release_all()
    core, *fx = a.config.split('+')
    wordfix.apply(d, core, set(fx))
    base, prof = levels.profile(d)
    for _ in range(20):
        try:
            grp = {g['callback']: g for g in entities.groups(d, base)}
            break
        except Exception:
            time.sleep(0.5)
    ent = grp[a.group]['entities'] + a.slot * 0x80
    if a.ptr is not None:
        ent = d.u32(ent + a.ptr)
    rf = base + 0x240658
    st = {}

    def on_frame(t, new):
        d.buttons(square=True)
        return d.u32(rf) >= a.after
    lp = BreakLoop(d, base)
    lp.every_frame(on_frame)
    lp.run(120)
    # now stopped? BreakLoop resumes at end; pause, set breaks
    d.pause()
    fc = base + prof['frame_counter']
    addrs = [ent + int(o, 0) for o in a.offs.split(',')] + [fc]
    for ad in addrs:
        d.add_mem_breakpoint(ad, 4, write=True, change=False)
    hits, frames = [], 0
    try:
        d.resume_quiet()
        while frames < a.frames:
            ev = d.wait_event('cpu.stepping', timeout=5.0)
            if ev is None:
                ev = d.cpu()
                if not ev.get('stepping'):
                    continue
            pc = int(ev['pc'])
            ea, size, new = pending_store(d, pc)
            if ea == fc:
                frames += 1
                hits.append({'frame': frames, 'ticks': int(ev['ticks']), 'rf': d.u32(rf)})
            else:
                regs = {n: R(d, 0, i) for n, i in (('ra', 31), ('sp', 29), ('a0', 4), ('s0', 16), ('s1', 17))}
                stack = [d.u32(regs['sp'] + 4 * k) for k in range(48)]
                hits.append({'pc': hex(pc - base), 'ra': hex(regs['ra'] - base), 'off': hex(ea - ent),
                             'old': struct.unpack('<f', struct.pack('<I', d.u32(ea)))[0],
                             'new': struct.unpack('<f', struct.pack('<I', new))[0],
                             'a0': hex(regs['a0']), 's0': hex(regs['s0']), 'ent': hex(ent),
                             'stack_code': [hex(w - base) for w in stack if base <= w < base + 0x200000]})
            d.resume_quiet()
    finally:
        for ad in addrs:
            d.remove_mem_breakpoint(ad, 4)
        d.release_all()
        if d.cpu().get('stepping'):
            d.resume()
a.out.write_text(json.dumps(hits, indent=1))
for h in hits:
    print(h)
