"""Frame-counter break diagnostic: N frames of break/resume, printing what each wait returns.
python fcdiag.py [--frames 40]
"""
import argparse, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tools/bench'))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa
import levels  # noqa
from breakloop import pending_store  # noqa

ap = argparse.ArgumentParser()
ap.add_argument('--frames', type=int, default=40)
ap.add_argument('--speed', type=float, default=0, help='only measure emulated / wall speed over this many wall s')
a = ap.parse_args()
with Debugger(DEFAULT_PORT).connect() as d:
    if a.speed:
        t0, k0 = time.monotonic(), int(d.cpu()['ticks'])
        time.sleep(a.speed)
        t1, k1 = time.monotonic(), int(d.cpu()['ticks'])
        print(f'emulated {(k1 - k0) / 222e6:.2f} s in {t1 - t0:.2f} wall s: x{(k1 - k0) / 222e6 / (t1 - t0):.2f}')
        raise SystemExit
    base, prof = levels.profile(d)
    fc = base + prof['frame_counter']
    print('cpu', d.cpu(), 'fc', hex(fc))
    d.pause()
    d.add_mem_breakpoint(fc, 4, write=True, change=True)
    d.resume_quiet()
    n, t0 = 0, time.monotonic()
    try:
        while n < a.frames and time.monotonic() - t0 < 60:
            ev = d.wait_event('cpu.stepping', timeout=1.0)
            st = d.cpu() if ev is None else None
            if ev is None:
                print(f'{time.monotonic() - t0:6.2f}s none; status stepping={st.get("stepping")} paused={st.get("paused")} '
                      f'ticks={st["ticks"]} pc={int(st["pc"]) - base:#x} queued={[m.get("event") for m in d.events][-5:]}')
                if not st.get('stepping'):
                    continue
                ev = st
            ea, size, new = pending_store(d, int(ev['pc']))
            kinds = {}
            for m in d.events:
                kinds[m.get('event')] = kinds.get(m.get('event'), 0) + 1
            sample = next((m for m in reversed(d.events) if m.get('event') == 'log'), None)
            print(f'{time.monotonic() - t0:6.2f}s break pc={int(ev["pc"]) - base:#x} ea={ea:#x} new={new} ticks={ev["ticks"]} '
                  f'queued={kinds} last log={str(sample)[:200]}')
            d.events.clear()
            n += 1
            d.resume_quiet()
    finally:
        d.remove_mem_breakpoint(fc, 4)
        if d.cpu().get('stepping'):
            d.resume()
