"""Double-tap window of the LEVEL_22 D-pad detector (0x1056E8), measured per config.

The race leaves the button-enable mask read by 0x68360 at 0x2000, so 0x68260(0x10) never returns the
up bit and the detector never sees the D-pad (paddiag.py). This script ORs 0x10 into that mask every
frame (an intervention, reported as such), then runs one test per gap: up held HOLD vblanks, released
GAP vblanks, held HOLD vblanks again. A test starts only when the detector runs (call counter 0x240658
advanced over the last 8 vblanks) and is idle (0x24064C == 0): an accepted double tap suspends it for
hundreds of vblanks; a refused one leaves it armed, so a press older than 70 calls also counts as idle.

Outcome per test, from the detector words: 'accepted' when 0x24064C returns to 0 after the 2nd press,
'refused' when the 2nd press re-arms it (0x240648 takes a new value, 0x24064C stays 0x10), 'missed'
otherwise. dCalls = calls between the two registered presses.

python tapwin.py --state banc-skyboard-arrive --config C1+tapwin --gaps 4,16,20 --out FILE.json
"""
import argparse, json, struct, sys, time
from pathlib import Path
BENCH = Path('D:/sandboxes/racsm60fps/wt-banc/tools/bench')
sys.path.insert(0, str(BENCH))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa
from breakloop import BreakLoop  # noqa
import states, wordfix, levels  # noqa

VB = 3_703_700
HOLD, SETTLE = 6, 16
ap = argparse.ArgumentParser()
ap.add_argument('--state', required=True)
ap.add_argument('--config', default='A0')
ap.add_argument('--gaps', default='4,16,20,22,24,26,30,46,50,52,54,56,60')
ap.add_argument('--seconds', type=float, default=130.0, help='emulated limit (C1 race ends at ~136 s)')
ap.add_argument('--out', type=Path, required=True)
a = ap.parse_args()
a.out.parent.mkdir(parents=True, exist_ok=True)
gaps = [int(g) for g in a.gaps.split(',')]
if a.state != '-':
    states.load(a.state)
    time.sleep(1.0)
with Debugger(DEFAULT_PORT).connect() as d:
    d.release_all()
    core, *fx = a.config.split('+')
    applied = wordfix.apply(d, core, set(fx))
    base, prof = levels.profile(d)
    hi, lo = (d.u32(base + 0x68360) & 0xFFFF) << 16, d.u32(base + 0x68364) & 0xFFFF
    mask_addr = (hi + (lo - 0x10000 if lo & 0x8000 else lo)) & 0xFFFFFFFF

    def i32(rva):
        return struct.unpack('<i', d.read(base + rva, 4))[0]

    st = {'t0': None, 'k': 0, 'phase': 'wait', 'at': 0, 'forced': 0, 'hist': []}
    tests, trace = [], []

    def on_frame(t, value):
        if value is None:
            return
        if st['t0'] is None:
            st['t0'] = t
        v = round((t - st['t0']) / VB)
        mask = d.u32(mask_addr)
        if not mask & 0x10:
            d.write_u32(mask_addr, mask | 0x10)
            st['forced'] += 1
        rf, last, btn = i32(0x240658), i32(0x240648), i32(0x24064C)
        trace.append([v, rf, last, btn, mask])
        st['hist'] = (st['hist'] + [rf])[-9:]
        if rf < 90:
            return
        ph, k = st['phase'], st['k']
        if ph == 'wait':
            running = len(st['hist']) == 9 and st['hist'][-1] - st['hist'][0] >= 3
            # idle, or armed by a press older than any window (a refused 2nd press leaves it armed)
            if running and (btn == 0 or rf - last > 70):
                d.buttons(up=True)
                tests.append({'test': k, 'gap': gaps[k], 'down': v, 'count': rf})
                st.update(phase='hold1', at=v)
        elif ph == 'hold1' and v - st['at'] >= HOLD:
            d.buttons(up=False)
            tests[-1].update(up=v, first=(last, btn))
            st.update(phase='gap', at=v)
        elif ph == 'gap' and v - st['at'] >= gaps[k]:
            d.buttons(up=True)
            tests[-1].update(down2=v, count2=rf, before2=(last, btn))
            st.update(phase='hold2', at=v)
        elif ph == 'hold2' and v - st['at'] >= HOLD:
            d.buttons(up=False)
            tests[-1].update(up2=v)
            st.update(phase='settle', at=v)
        elif ph == 'settle' and v - st['at'] >= SETTLE:
            r = tests[-1]
            l1, b1 = r['before2']
            if b1 != 0x10:
                out = 'missed'          # first press never registered
            elif btn == 0:
                out = 'accepted'
            elif last != l1:
                out = 'refused'
            else:
                out = 'missed'
            # calls between registered presses: the 2nd press registers at the first frame after down2
            reg2 = next((row[1] for row in trace if row[0] >= r['down2'] and (row[3] == 0 or row[2] != l1)), None)
            r.update(read=v, last=last, button=btn, outcome=out, firstLast=l1, call2=reg2,
                     dCalls=None if reg2 is None else reg2 - l1, pressToPressV=r['down2'] - r['down'])
            print(a.config, r)
            st.update(phase='wait', k=k + 1, hist=[])
            return k + 1 >= len(gaps)

    loop = BreakLoop(d, base)
    loop.every_frame(on_frame)
    loop.at_end(lambda: d.release_all())
    loop.run(a.seconds, wall_limit=a.seconds * 6)
a.out.write_text(json.dumps({'config': a.config, 'applied': applied['fixes'], 'writes': len(applied['writes']),
                             'maskAddr': hex(mask_addr), 'maskForcedFrames': st['forced'], 'hold': HOLD,
                             'tests': tests, 'trace': trace}) + '\n')
print('mask', hex(mask_addr), 'forced', st['forced'], 'frames; tests', len(tests))
for r in tests:
    print(a.config, 'gap', r['gap'], 'p2p', r.get('pressToPressV'), 'dCalls', r.get('dCalls'), r.get('outcome'))
