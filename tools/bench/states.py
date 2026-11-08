#!/usr/bin/env python3
"""Named savestates for the bench instance (Windows, PPSSPP 1.20.4).

The 1.20.4 debugger API has no savestate request, so this drives the PPSSPP
window menu commands instead (PostMessage WM_COMMAND, no focus needed):
  slot select  ID_FILE_SAVESTATE_SLOT_BASE + n  (45000 + n)
  quick save   ID_FILE_QUICKSAVESTATE           (40034)
  quick load   ID_FILE_QUICKLOADSTATE           (40035)
(IDs from Windows/resource.h at tag v1.20.4.) A named state is the slot file
copied to <root>/work/states/<name>.ppst; loading copies it back into the slot
and triggers a quick load. Boot-time loading is also possible with
`PPSSPPWindows64.exe --state=<file> <iso>`.

Savestates are game-derived content: they stay in work/, never in Git.

Usage:
  python tools/bench/states.py save --name pokitaru-beach
  python tools/bench/states.py load --name pokitaru-beach
  python tools/bench/states.py list

Both commands are checked against the emulated clock (2026-11-08, after a load
that silently did not happen and a "pre-climb" save taken ~7 s late):
- `save` records the CPU ticks around the quick save in <name>.json. Called while
  the CPU is stopped at a breakpoint (pass the connected Debugger), PPSSPP still
  processes the save, so the state is the exact stopped instant (ticks equal).
- `load` waits until the ticks jump (backwards, or forwards faster than the
  emulator can run), re-posts the quick load once, and raises if the clock never
  jumps; with a sidecar it also checks the ticks land on the saved ones.
- `load(pause=True)` stops the CPU before the load and leaves it stopped at the
  loaded instant (exact ticks), for scripts whose first frame must be the saved one.
"""
import argparse
import ctypes
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wincap  # noqa: E402
from ppsspp_bench import DEFAULT_INSTANCE, DEFAULT_PORT, DEFAULT_ROOT, Debugger  # noqa: E402

CPU_HZ = 222_000_000          # same as breakloop.CPU_HZ (not imported: breakloop pulls levels)

WM_COMMAND = 0x0111
ID_QUICKSAVE, ID_QUICKLOAD, ID_SLOT_BASE = 40034, 40035, 45000
GAME_PREFIX = 'UCES00420_1.00'
SLOT = 4                      # bench-owned slot (the last of the default five)
STATES = DEFAULT_ROOT / 'work/states'


def _hwnd(instance):
    pid = int((Path(instance) / 'bench.pid').read_text(encoding='ascii'))
    hwnd = wincap.main_window(pid)
    if not hwnd:
        raise RuntimeError(f'no window for pid {pid}')
    return hwnd


def _post(hwnd, cmd):
    if not ctypes.windll.user32.PostMessageW(hwnd, WM_COMMAND, cmd, 0):
        raise RuntimeError(f'PostMessage {cmd} failed')


def slot_file(instance, slot=SLOT):
    return Path(instance) / f'memstick/PSP/PPSSPP_STATE/{GAME_PREFIX}_{slot}.ppst'


def _ticks(d):
    return int(d.cpu()['ticks'])


def save(name, instance=DEFAULT_INSTANCE, timeout=20.0, d=None, port=DEFAULT_PORT):
    """Quick save to <root>/work/states/<name>.ppst plus <name>.json (ticks around the save).
    `d`: an already connected Debugger (e.g. stopped at a frame break), else one is opened."""
    if d is None:
        with Debugger(port).connect() as d2:
            return save(name, instance, timeout, d2, port)
    out = STATES / f'{name}.ppst'
    if out.exists():
        raise RuntimeError(f'refusing to overwrite {out}')
    t_before = _ticks(d)
    stepping = bool(d.cpu().get('stepping'))
    hwnd = _hwnd(instance)
    f = slot_file(instance)
    before = f.stat().st_mtime if f.exists() else 0
    _post(hwnd, ID_SLOT_BASE + SLOT)
    time.sleep(0.3)
    _post(hwnd, ID_QUICKSAVE)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if f.exists() and f.stat().st_mtime > before:
            time.sleep(1.0)     # let the writer finish
            size = f.stat().st_size
            time.sleep(0.5)
            if f.stat().st_size == size:
                break
        time.sleep(0.25)
    else:
        raise RuntimeError('savestate file did not appear')
    t_after = _ticks(d)
    STATES.mkdir(parents=True, exist_ok=True)
    shutil.copy2(f, out)
    side = {'ticksBefore': t_before, 'ticksAfter': t_after, 'stoppedAtSave': stepping and t_before == t_after}
    out.with_suffix('.json').write_text(json.dumps(side) + '\n')
    return out


def _jumped(d, timeout):
    """True once the emulated clock jumps (a load happened) within `timeout` wall seconds."""
    prev_t, prev_w = _ticks(d), time.monotonic()
    deadline = prev_w + timeout
    while time.monotonic() < deadline:
        time.sleep(0.1)
        t, w = _ticks(d), time.monotonic()
        # the bench runs at x1 (measured x1.00 on 2026-11-08); x3 + 0.1 s leaves room for catch-up
        if t < prev_t or t - prev_t > (w - prev_w) * CPU_HZ * 3 + CPU_HZ // 10:
            return True
        prev_t, prev_w = t, w
    return False


def _changed(d, t_old, timeout):
    """With the CPU stopped: True once the ticks differ from t_old (PPSSPP loads while stepping)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(0.1)
        if _ticks(d) != t_old:
            return True
    return False


def load(name, instance=DEFAULT_INSTANCE, port=DEFAULT_PORT, settle=2.0, pause=False):
    """Quick load <name>; raise unless the emulated clock shows the load (see the module doc).
    pause=True: stop the CPU first and leave it stopped at the loaded instant (no free-running
    frames before the caller's script starts, README pitfall 19); no settle sleep then."""
    src = STATES / f'{name}.ppst'
    if not src.exists():
        raise RuntimeError(f'no state {src}')
    side = src.with_suffix('.json')
    side = json.loads(side.read_text()) if side.exists() else None
    hwnd = _hwnd(instance)
    f = slot_file(instance)
    f.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, f)
    with Debugger(port).connect() as d:
        stopped = bool(d.cpu().get('stepping'))
        if pause and not stopped:
            d.pause()
        elif not pause and stopped:
            d.resume()          # running clock: the jump check below needs it
        t_start = time.monotonic()
        for attempt in range(2):
            t_old = _ticks(d)
            _post(hwnd, ID_SLOT_BASE + SLOT)
            time.sleep(0.3)
            _post(hwnd, ID_QUICKLOAD)
            if (_changed(d, t_old, 6.0) if pause else _jumped(d, 6.0)):
                break
        else:
            raise RuntimeError(f'state {name}: the emulated clock never jumped after two quick loads')
        if side:
            t = _ticks(d)
            lo = side['ticksBefore']
            hi = side['ticksAfter'] + (0 if pause else int((time.monotonic() - t_start + 1) * CPU_HZ * 3))
            if not lo <= t <= hi:
                raise RuntimeError(f'state {name}: ticks {t} after the load, expected {lo}..{hi}')
    rest = 0 if pause else settle - (time.monotonic() - t_start)
    if rest > 0:
        time.sleep(rest)
    return src


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=('save', 'load', 'list'))
    ap.add_argument('--name')
    ap.add_argument('--instance', default=str(DEFAULT_INSTANCE))
    a = ap.parse_args()
    if a.cmd == 'list':
        for p in sorted(STATES.glob('*.ppst')):
            print(f'{p.stem:40s} {p.stat().st_size:>10d}')
        return
    if not a.name or not a.name.replace('-', '').replace('_', '').isalnum():
        raise SystemExit('--name: letters, digits, - and _ only')
    print(save(a.name, a.instance) if a.cmd == 'save' else load(a.name, a.instance))


if __name__ == '__main__':
    main()
