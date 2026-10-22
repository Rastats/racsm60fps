#!/usr/bin/env python3
"""Render-only interpolation prototype for LEVEL_01, driven by the PPSSPP debugger.

Exploratory, no plugin. Apply a config first (A0 from the savestate, C1 or G1 with
tools/runtime/pump-gate.py), then run this script. It stops the CPU at render
entry (0x156DC, called from the gameplay dispatcher at 0x15AB0) and after the
render call, so emulated time is frozen while it reads or writes memory.

mode observe  records, at each render, the world matrix translation of tracked
              pump-1 entities (what the draw reads, see ../REPORT.md).
mode interp   (G1 only) keeps the last two logic states of every pump-1 entity
              world matrix (+0x00..+0x3F). On a frame where the gated pump ran it
              writes lerp(previous, current, 0.5) into the entities for the render
              pass, then restores the exact bytes read at entry; on a skipped
              frame the current state is drawn. The authoritative state the next
              update reads is therefore the game's own (one 60 Hz frame of display
              delay for world entities). Entities seen moving on a frame where the
              pump did not run are driven at 60 Hz elsewhere (Ratchet's moby) and
              are never blended. Snap rule: no blend when the translation
              jumps more than --snap units in one logic tick, or when the entity is
              inactive (+0x64 bit 0) in either state.

Usage:
  python interp_proto.py --port 60909 --mode observe --frames 120 --track 16:0 --track 40:3 --out <dir>
  python interp_proto.py --port 60909 --mode interp  --frames 120 --track 16:0 --out <dir> [--shots 40]
"""
import argparse
import base64
import hashlib
import json
import math
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / 'tools/bench'))
sys.path.insert(0, str(HERE))
from ppsspp_bench import Debugger, BenchError  # noqa: E402
from entities import groups  # noqa: E402
from render_probe import Boundary, level_base, shot  # noqa: E402

GATE_STATE = 0x2C2400            # tools/runtime/pump-gate.py: mode, phase, accum, runs, skips
MAT = 0x40                       # entity world matrix, row 3 = translation (OBSERVED 2026-10-22)


def span_of(gs):
    lo = min(g['entities'] for g in gs)
    hi = max(g['entities'] + g['capacity'] * 0x80 for g in gs)
    return lo, hi - lo


def matrices(raw, lo, gs):
    """{(group, slot): (16 floats, active)} for every entity slot of the given groups."""
    out = {}
    for g in gs:
        off = g['entities'] - lo
        for k in range(g['capacity']):
            o = off + k * 0x80
            m = struct.unpack_from('<16f', raw, o)
            flags, = struct.unpack_from('<I', raw, o + 0x64)
            out[(g['i'], k)] = (m, flags & 1)
    return out


def blend(prev, cur, snap):
    m0, a0 = prev
    m1, a1 = cur
    if not (a0 and a1):
        return None
    if not all(math.isfinite(v) for v in m0 + m1):
        return None
    if math.dist(m0[12:15], m1[12:15]) > snap:
        return None
    if m0 == m1:
        return None
    return tuple(x + (y - x) * 0.5 for x, y in zip(m0, m1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--mode', choices=('observe', 'interp'), required=True)
    ap.add_argument('--frames', type=int, default=120)
    ap.add_argument('--track', action='append', default=[], help='group:slot')
    ap.add_argument('--snap', type=float, default=4.0)
    ap.add_argument('--no-exempt', action='store_true',
                    help='also blend entities that move on frames without a pump run (60 Hz-driven)')
    ap.add_argument('--shots', type=int, default=0, help='window captures of the first N renders')
    ap.add_argument('--instance', default='D:/sandboxes/racsm60fps/emu/ppsspp-3')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    track = [tuple(int(x) for x in t.split(':')) for t in a.track]

    with Debugger(a.port).connect() as d:
        base = level_base(d)
        gs = [g for g in groups(d, base) if g['entities'] and 0 < g['capacity'] <= 512]
        lo, size = span_of(gs)
        gate_addr = base + GATE_STATE
        rows, writes, stats = [], {}, {'blended_frames': 0, 'blended_matrices': 0, 'snapped': 0}
        hist = {'prev': None, 'cur': None, 'runs': None, 'last': None}
        live60 = set()          # entities whose matrix changed on a frame where the gated pump did not run
        entry_raw = {}

        def gate_runs():
            mode, phase, accum, runs, skips = struct.unpack('<5I', d.read(gate_addr, 20))
            return runs if mode == 1 else None

        def on_entry(t, ra):
            raw = d.read(lo, size)
            entry_raw['raw'] = raw
            state = matrices(raw, lo, gs)
            runs = gate_runs()
            ran = runs is None or runs != hist['runs']
            hist['runs'] = runs
            if ran:
                hist['prev'], hist['cur'] = hist['cur'], state
            elif hist['last'] is not None and not a.no_exempt:
                for key, cur in state.items():
                    if key not in live60 and hist['last'].get(key) is not None and hist['last'][key][0] != cur[0]:
                        live60.add(key)
            hist['last'] = state
            drawn = {}
            if a.mode == 'interp' and runs is not None and ran and hist['prev'] is not None:
                buf = bytearray(raw)
                n = 0
                for key, cur in state.items():
                    prev = hist['prev'].get(key)
                    if prev is None or key in live60:
                        continue
                    m = blend(prev, cur, a.snap)
                    if m is None:
                        if cur[1] and prev[1] and math.dist(prev[0][12:15], cur[0][12:15]) > a.snap:
                            stats['snapped'] += 1
                        continue
                    g = next(x for x in gs if x['i'] == key[0])
                    o = g['entities'] - lo + key[1] * 0x80
                    struct.pack_into('<16f', buf, o, *m)
                    drawn[key] = m
                    n += 1
                if n:
                    d.call('memory.write', address=lo, base64=base64.b64encode(bytes(buf)).decode('ascii'))
                    stats['blended_frames'] += 1
                    stats['blended_matrices'] += n
            # digest of the authoritative entity span as the update left it (before any blend)
            row = {'t': t, 'ran': ran, 'runs': runs, 'span_sha1': hashlib.sha1(raw).hexdigest()}
            for key in track:
                auth = state[key][0][12:15]
                shown = drawn.get(key, state[key][0])[12:15]
                row['%d:%d' % key] = {'auth': [round(v, 5) for v in auth], 'drawn': [round(v, 5) for v in shown]}
            rows.append(row)

        def on_exit(t, pc):
            if a.mode == 'interp' and d.read(lo, size) != entry_raw['raw']:
                d.call('memory.write', address=lo, base64=base64.b64encode(entry_raw['raw']).decode('ascii'))
                writes['restores'] = writes.get('restores', 0) + 1
            if len(rows) <= a.shots:
                shot(d, a.instance, out / ('f%03d.png' % len(rows)))

        b = Boundary(d, base)
        t0 = time.monotonic()
        try:
            b.run(a.frames, on_entry=on_entry, on_exit=on_exit, wall=max(300.0, a.frames * 3.0))
        finally:
            if d.cpu().get('stepping'):
                d.resume()
        res = {'mode': a.mode, 'base': hex(base), 'span': [hex(lo), hex(size)], 'groups': len(gs),
               'frames': len(rows), 'wall_s': round(time.monotonic() - t0, 1), 'stats': stats, 'writes': writes,
               'track': a.track,
               'live60': sorted('%d:%d' % k for k in live60)}
        (out / 'rows.json').write_text(json.dumps(rows, indent=0), encoding='utf-8')
        (out / 'result.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
        print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
