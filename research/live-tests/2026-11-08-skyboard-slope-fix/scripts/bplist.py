"""List (and with --clear remove) the CPU and memory breakpoints left in the bench PPSSPP.
python bplist.py [--clear]
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tools/bench'))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa

ap = argparse.ArgumentParser()
ap.add_argument('--clear', action='store_true')
a = ap.parse_args()
with Debugger(DEFAULT_PORT).connect() as d:
    mem = d.call('memory.breakpoint.list').get('breakpoints', [])
    cpu = d.call('cpu.breakpoint.list').get('breakpoints', [])
    print('memory', json.dumps(mem))
    print('cpu', json.dumps(cpu))
    if a.clear:
        for b in mem:
            d.remove_mem_breakpoint(b['address'], b['size'])
        for b in cpu:
            d.call('cpu.breakpoint.remove', address=b['address'])
        print('cleared', len(mem), len(cpu))
