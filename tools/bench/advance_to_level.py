#!/usr/bin/env python3
"""Advance through dialogs and cutscenes until a given level module is resident.

Every level is loaded as the module `rcp1`; the level is identified by the
module size (LEVEL_01 Pokitaru: 0x46B900, see tools/runtime/pump-gate.py).
While the target is not resident the script presses a button every few seconds
(default: circle, then start to skip cutscenes). It stops pressing as soon as
the target module appears, then waits for the level to be playable (the game
frame counter advancing).

Usage:
  python tools/bench/advance_to_level.py --size 0x46B900 --timeout 300
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ppsspp_bench import Debugger, DEFAULT_PORT  # noqa: E402


def resident_size(d):
    mods = [m for m in d.modules() if m['name'] == 'rcp1']
    return mods[0]['size'] if len(mods) == 1 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--size', default='0x46B900', help='rcp1 module size of the target level')
    ap.add_argument('--buttons', default='circle,start', help='buttons pressed in turn while waiting')
    ap.add_argument('--every', type=float, default=3.0, help='seconds between presses')
    ap.add_argument('--timeout', type=float, default=300.0)
    a = ap.parse_args()
    target = int(a.size, 0)
    buttons = [b for b in a.buttons.split(',') if b]
    log = []
    with Debugger(a.port).connect() as d:
        deadline = time.monotonic() + a.timeout
        i = 0
        while time.monotonic() < deadline:
            size = resident_size(d)
            if size == target:
                break
            b = buttons[i % len(buttons)]
            d.press(b, 3)
            log.append({'t': round(time.monotonic(), 1), 'press': b, 'rcp1': hex(size) if size else None})
            i += 1
            time.sleep(a.every)
        else:
            print(json.dumps({'result': 'TIMEOUT', 'log': log[-10:]}))
            return 1
        mod = d.module('rcp1')
        print(json.dumps({'result': 'RESIDENT', 'base': hex(mod['address']), 'size': hex(mod['size']),
                          'presses': len(log), 'ticks': d.ticks()}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
