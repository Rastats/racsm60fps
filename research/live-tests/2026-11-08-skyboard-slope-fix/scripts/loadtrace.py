"""Trace the emulated clock and the player position around one quick load (bench diagnostic).
python loadtrace.py STATE [--seconds 8]
"""
import argparse, shutil, struct, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tools/bench'))
from ppsspp_bench import Debugger, DEFAULT_PORT, DEFAULT_INSTANCE  # noqa
import states, levels  # noqa

ap = argparse.ArgumentParser()
ap.add_argument('state')
ap.add_argument('--seconds', type=float, default=8)
a = ap.parse_args()
src = states.STATES / f'{a.state}.ppst'
with Debugger(DEFAULT_PORT).connect() as d:
    base, prof = levels.profile(d)
    pos = base + prof['player'] + 0x30

    def snap(tag):
        st = d.cpu()
        p = struct.unpack('<3f', d.read(pos, 12))
        print(f'{time.monotonic() - t0:6.2f} {tag:8s} ticks {int(st["ticks"]):>13d} stepping {st.get("stepping")} '
              f'pos {[round(c, 2) for c in p]}', flush=True)
    t0 = time.monotonic()
    snap('before')
    shutil.copy2(src, states.slot_file(DEFAULT_INSTANCE))
    hwnd = states._hwnd(DEFAULT_INSTANCE)
    states._post(hwnd, states.ID_SLOT_BASE + states.SLOT)
    time.sleep(0.3)
    states._post(hwnd, states.ID_QUICKLOAD)
    snap('posted')
    while time.monotonic() - t0 < a.seconds:
        time.sleep(0.2)
        snap('')
