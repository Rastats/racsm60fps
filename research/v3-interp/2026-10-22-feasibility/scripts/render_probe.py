#!/usr/bin/env python3
"""Live probes of the LEVEL_01 update/render boundary (PPSSPP debugger, no plugin).

The gameplay frame dispatcher 0x159DC calls the update 0x1517C, then the render
pass 0x156DC (static map: ../REPORT.md). These probes stop the CPU at render
entry and at the instruction after the render call, so emulated time is frozen
while the script reads or writes memory.

Modes:
  callers  count render/update entries per caller (which dispatcher case runs)
  lift     add an offset to an entity's matrix translation (+0x30..+0x38) for the
           render pass only, restore it after; window captures with and without.
           If the drawn entity moves, the draw reads the live transform.
  purity   write memchecks armed only during the render pass on given ranges;
           any hit is state written by the render pass.

Usage (instance from tools/bench; RACSM_ROOT for the layout):
  python render_probe.py --port 60909 callers --frames 120
  python render_probe.py --port 60909 lift --entity 0x96fe770 --dx 1.5 --frames 30 --out <dir>
  python render_probe.py --port 60909 purity --range 0x96fe770:0x80 --frames 60 --out <dir>
"""
import argparse
import json
import struct
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / 'tools/bench'))
from ppsspp_bench import Debugger, BenchError  # noqa: E402
import wincap  # noqa: E402

LEVEL01_SIZE = 0x46B900
UPDATE, RENDER = 0x1517C, 0x156DC


class Boundary:
    """CPU breakpoints at render entry and at each return site seen (ra at entry)."""

    def __init__(self, d, base, extra=()):
        self.d, self.base = d, base
        self.entry = base + RENDER
        self.exits = set()
        self.extra = set(base + r for r in extra)

    def reg(self, name):
        return int(self.d.call('cpu.getReg', name=name)['uintValue'])

    def run(self, frames, on_entry=None, on_exit=None, on_other=None, wall=120.0):
        d = self.d
        d.pause()
        d.add_cpu_breakpoint(self.entry)
        for a in [*self.extra, *self.exits]:
            d.add_cpu_breakpoint(a)
        d.call('cpu.breakpoint.list')   # round trip: without it only the last added breakpoint fired (2026-10-22)
        n = 0
        deadline = time.monotonic() + wall
        try:
            d.resume_quiet()
            while n < frames:
                if time.monotonic() > deadline:
                    raise BenchError('wall-clock limit')
                ev = d.wait_event('cpu.stepping', timeout=2.0)
                if ev is None:
                    continue
                pc = int(ev['pc'])
                if pc == self.entry:
                    ra = self.reg('ra')
                    if ra not in self.exits:
                        self.exits.add(ra)
                        d.add_cpu_breakpoint(ra)
                        d.call('cpu.breakpoint.list')
                    if on_entry:
                        on_entry(int(ev['ticks']), ra)
                elif pc in self.exits:
                    n += 1
                    if on_exit:
                        on_exit(int(ev['ticks']), pc)
                    if n >= frames:
                        break               # leave the CPU stopped after the last render
                elif on_other:
                    on_other(int(ev['ticks']), pc)
                d.resume_quiet()
        finally:
            for a in [self.entry, *self.exits, *self.extra]:
                d.remove_cpu_breakpoint(a)
        return n


def level_base(d):
    m = d.module('rcp1')
    if m['size'] != LEVEL01_SIZE:
        raise BenchError('LEVEL_01 must be resident')
    return m['address']


def cmd_callers(d, base, a):
    seen = {}
    b = Boundary(d, base, extra=(UPDATE,))

    def entry(t, ra):
        k = 'render<-0x%X' % (ra - 8 - base)
        seen[k] = seen.get(k, 0) + 1

    def other(t, pc):
        if pc == base + UPDATE:
            ra = b.reg('ra')
            k = 'update<-0x%X' % (ra - 8 - base)
            seen[k] = seen.get(k, 0) + 1

    b.run(a.frames, on_entry=entry, on_other=other)
    d.resume()
    return {'frames': a.frames, 'calls': seen}


def shot(d, instance, path):
    pid = int((Path(instance) / 'bench.pid').read_text(encoding='ascii'))
    time.sleep(0.3)
    wincap.capture(pid, path)
    return str(path)


def cmd_lift(d, base, a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    pos = int(a.entity, 16) + 0x30 + 4 * a.axis
    log = []
    b = Boundary(d, base)

    def entry(t, ra):
        v, = struct.unpack('<f', d.read(pos, 4))
        log.append({'t': t, 'before': v})
        d.call('memory.write_u32', address=pos, value=struct.unpack('<I', struct.pack('<f', v + a.dx))[0])
        entry.saved = v

    def exit_(t, pc):
        cur, = struct.unpack('<f', d.read(pos, 4))
        log[-1]['during_end'] = cur
        d.call('memory.write_u32', address=pos, value=struct.unpack('<I', struct.pack('<f', entry.saved))[0])

    # reference: same stop point, no offset
    b.run(a.frames)
    ref = shot(d, a.instance, out / 'ref.png')
    d.resume()
    b.run(a.frames, on_entry=entry, on_exit=exit_)
    lifted = shot(d, a.instance, out / 'lifted.png')
    after, = struct.unpack('<f', d.read(pos, 4))
    d.resume()
    # the render pass must leave the offset value untouched (no copy written back)
    leaked = [r for r in log if abs(r['during_end'] - (r['before'] + a.dx)) > 1e-6]
    res = {'entity': a.entity, 'axis': a.axis, 'dx': a.dx, 'frames': len(log), 'ref': ref, 'lifted': lifted,
           'value_after_restore': after, 'render_rewrote_offset_value': len(leaked), 'sample': log[:3]}
    (out / 'lift.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    return res


def cmd_purity(d, base, a):
    """Write memchecks armed during one phase only. --phase update is the positive
    control: the same ranges must report the update's own stores."""
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    ranges = []
    for r in a.range:
        addr, size = r.split(':')
        ranges.append((int(addr, 16), int(size, 16)))
    hits = {}
    armed = [False]
    b = Boundary(d, base)

    def arm():
        if not armed[0]:
            for addr, size in ranges:
                d.add_mem_breakpoint(addr, size, write=a.access == 'write', read=a.access == 'read', change=False)
            armed[0] = True

    def disarm():
        if armed[0]:
            for addr, size in ranges:
                d.remove_mem_breakpoint(addr, size)
            armed[0] = False

    def entry(t, ra):
        (arm if a.phase == 'render' else disarm)()

    def exit_(t, pc):
        (disarm if a.phase == 'render' else arm)()

    def other(t, pc):
        k = '0x%X' % (pc - base) if base <= pc < base + LEVEL01_SIZE else hex(pc)
        hits[k] = hits.get(k, 0) + 1
        if sum(hits.values()) >= a.cap:
            disarm()

    try:
        b.run(a.frames, on_entry=entry, on_exit=exit_, on_other=other)
    finally:
        disarm()
        d.resume()
    res = {'phase': a.phase, 'access': a.access, 'ranges': [[hex(x), hex(s)] for x, s in ranges], 'frames': a.frames,
           'cap': a.cap, 'writes': hits}
    (out / 'purity.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, required=True)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('callers'); p.add_argument('--frames', type=int, default=120)
    p = sub.add_parser('lift'); p.add_argument('--entity', required=True); p.add_argument('--axis', type=int, default=0)
    p.add_argument('--dx', type=float, default=1.5); p.add_argument('--frames', type=int, default=30)
    p.add_argument('--out', required=True); p.add_argument('--instance', required=True)
    p = sub.add_parser('purity'); p.add_argument('--range', action='append', required=True)
    p.add_argument('--frames', type=int, default=60); p.add_argument('--out', required=True)
    p.add_argument('--phase', choices=('render', 'update'), default='render')
    p.add_argument('--access', choices=('write', 'read'), default='write')
    p.add_argument('--cap', type=int, default=300, help='disarm after this many hits')
    a = ap.parse_args()
    with Debugger(a.port).connect() as d:
        base = level_base(d)
        fn = {'callers': cmd_callers, 'lift': cmd_lift, 'purity': cmd_purity}[a.cmd]
        print(json.dumps(fn(d, base, a), indent=1))


if __name__ == '__main__':
    main()
