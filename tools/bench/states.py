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
"""
import argparse
import ctypes
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wincap  # noqa: E402
from ppsspp_bench import DEFAULT_INSTANCE, DEFAULT_ROOT  # noqa: E402

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


def save(name, instance=DEFAULT_INSTANCE, timeout=20.0):
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
    STATES.mkdir(parents=True, exist_ok=True)
    out = STATES / f'{name}.ppst'
    if out.exists():
        raise RuntimeError(f'refusing to overwrite {out}')
    shutil.copy2(f, out)
    return out


def load(name, instance=DEFAULT_INSTANCE):
    src = STATES / f'{name}.ppst'
    if not src.exists():
        raise RuntimeError(f'no state {src}')
    hwnd = _hwnd(instance)
    f = slot_file(instance)
    f.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, f)
    _post(hwnd, ID_SLOT_BASE + SLOT)
    time.sleep(0.3)
    _post(hwnd, ID_QUICKLOAD)
    time.sleep(2.0)
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
