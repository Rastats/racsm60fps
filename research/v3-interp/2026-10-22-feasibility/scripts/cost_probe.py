#!/usr/bin/env python3
"""Emulated CPU cost of InterpRender (../prx), measured with CPU breakpoints.

Breakpoints (emulated time is frozen while stopped, so they cost nothing):
  ir_pump entry, pump 1 entry, the return site in ir_pump, after the 0x15230 site;
  ir_render entry, render 0x156DC entry, the return site in ir_render, after 0x15AB0.
Per frame it derives the plugin's own work around the two game calls:
  pump_pre   ir_pump entry -> pump 1 entry (gate + snapshot), or -> after-site on skipped frames
  pump_post  pump 1 return -> after-site
  render_pre ir_render entry -> render entry (blend), render_post render return -> after-site (restore)
Ticks are PPSSPP CoreTiming cycles at 222 MHz; one 59.94 Hz vblank = 3,703,700.

Status: did not measure on PPSSPP 1.20.4. Only the last-added breakpoint fired, even
with a list round trip after each add (work/runs/interp-071, interp-073); see REPORT.md section 7.

Usage: python cost_probe.py --port 60909 --frames 120 --out <dir>
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ir_apply import locate, status, PUMP1, RENDER, SITE_PUMP, SITE_RENDER  # noqa: E402
from ppsspp_bench import Debugger, BenchError  # noqa: E402

VBLANK_TICKS = 3_703_700


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--frames', type=int, default=120)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    with Debugger(a.port).connect() as d:
        base, sym = locate(d)
        fixed = {sym['ir_pump']: 'pump_in', base + PUMP1: 'pump1', base + SITE_PUMP + 8: 'pump_out',
                 sym['ir_render']: 'render_in', base + RENDER: 'render', base + SITE_RENDER + 8: 'render_out'}
        dyn = {}
        frames, cur = [], {}
        d.pause()
        for addr in fixed:
            d.add_cpu_breakpoint(addr)
            d.call('cpu.breakpoint.list')      # one round trip per add (only the last add fired otherwise)
        listed = {b['address'] for b in d.call('cpu.breakpoint.list')['breakpoints']}
        if set(fixed) - listed:
            raise BenchError('breakpoints not registered: %s' % [hex(x) for x in set(fixed) - listed])
        t0 = time.monotonic()
        try:
            d.resume_quiet()
            while len(frames) < a.frames:
                if time.monotonic() - t0 > 600:
                    raise BenchError('wall-clock limit')
                ev = d.wait_event('cpu.stepping', timeout=2.0)
                if ev is None:
                    continue
                pc, t = int(ev['pc']), int(ev['ticks'])
                label = fixed.get(pc) or dyn.get(pc)
                if label in ('pump1', 'render'):
                    ra = int(d.call('cpu.getReg', name='ra')['uintValue'])
                    if ra not in dyn:
                        dyn[ra] = label + '_ret'
                        d.add_cpu_breakpoint(ra)
                        d.call('cpu.breakpoint.list')
                if label:
                    cur[label] = t
                if label == 'render_out':
                    frames.append(dict(cur))
                    cur = {}
                d.resume_quiet()
        finally:
            d.pause()
            for addr in [*fixed, *dyn]:
                d.remove_cpu_breakpoint(addr)
            d.resume()
        st = status(d, sym)

    def span(f, x, y):
        return f[y] - f[x] if x in f and y in f else None

    rows = []
    for f in frames[1:]:              # first record may start mid-frame
        ran = 'pump1' in f
        rows.append({
            'ran': ran,
            'pump_pre': span(f, 'pump_in', 'pump1') if ran else span(f, 'pump_in', 'pump_out'),
            'pump_post': span(f, 'pump1_ret', 'pump_out') if ran else 0,
            'render_pre': span(f, 'render_in', 'render'),
            'render_post': span(f, 'render_ret', 'render_out'),
            'render_out': f.get('render_out'),
        })
    periods = [b['render_out'] - a_['render_out'] for a_, b in zip(rows, rows[1:])]

    def stats(key, ran):
        v = [r[key] for r in rows if r['ran'] == ran and r[key] is not None]
        return {'n': len(v), 'mean': round(statistics.mean(v)) if v else None, 'max': max(v) if v else None}

    total_ran = [sum(r[k] or 0 for k in ('pump_pre', 'pump_post', 'render_pre', 'render_post')) for r in rows if r['ran']]
    total_skip = [sum(r[k] or 0 for k in ('pump_pre', 'pump_post', 'render_pre', 'render_post')) for r in rows if not r['ran']]
    res = {
        'mode': st['mode'], 'stat': st['stat'], 'frames': len(rows),
        'pump_ran': {k: stats(k, True) for k in ('pump_pre', 'pump_post', 'render_pre', 'render_post')},
        'pump_skipped': {k: stats(k, False) for k in ('pump_pre', 'pump_post', 'render_pre', 'render_post')},
        'plugin_ticks_per_frame_pair_mean': round(statistics.mean(total_ran) + statistics.mean(total_skip))
        if total_ran and total_skip else None,
        'plugin_share_of_two_vblanks_pct': round(100 * (statistics.mean(total_ran) + statistics.mean(total_skip))
                                                 / (2 * VBLANK_TICKS), 3) if total_ran and total_skip else None,
        'frame_period_ticks': {'min': min(periods), 'max': max(periods),
                               'mean': round(statistics.mean(periods))} if periods else None,
    }
    (out / 'frames.json').write_text(json.dumps(rows, indent=0), encoding='utf-8')
    (out / 'cost.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
