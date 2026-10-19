#!/usr/bin/env python3
"""Create an isolated, portable PPSSPP instance for automated measurements.

Why: automated runs must not touch the owner's own PPSSPP configuration
(Documents/PPSSPP), and several instances may run side by side, each on its
own debugger port. PPSSPP on Windows runs in portable mode when the file
`installed.txt` is absent next to the executable: the memory stick then lives
in `<instance>/memstick/`, with its own ppsspp.ini, plugins and savestates.

What it does:
  1. copies an installed PPSSPP (default: C:/Program Files/PPSSPP) without
     installed.txt and the uninstaller;
  2. writes `memstick/PSP/SYSTEM/ppsspp.ini` with the automation settings
     below (PPSSPP fills in defaults for every other key on first run).

Security note (checked in PPSSPP sources, Core/WebServer.cpp and
Common/Net/HTTPServer.cpp, 2026-10-19): the debugger web server listens on
all interfaces (INADDR_ANY) without authentication, and it registers the
machine's LAN address and port with report.ppsspp.org (used by the official
remote-debugger UI to discover instances). Leave the Windows firewall prompt
for the copied executable unanswered or denied: local (127.0.0.1) clients work
either way. "RemoteDebuggerLocal" only selects a locally hosted debugger UI; it
does not restrict the listening address.

Usage:
  python tools/env/setup_ppsspp_portable.py --dest D:/racsm60fps/emu/ppsspp-1 --port 60907
"""
import argparse
import shutil
from pathlib import Path

SKIP = {'installed.txt', 'unins000.exe', 'unins000.dat', 'unins000.msg'}

# Minimal ini: only keys that matter for automation. Section order is free.
INI = """[General]
FirstRun = False
CheckForNewVersion = False
DiscordRichPresence = False
AutoRun = True
IgnoreBadMemAccess = True
EnableCheats = False
EnablePlugins = {plugins}
LoadPlugins = {plugins}
RemoteISOPort = {port}
RemoteDebuggerOnStartup = True
RemoteShareOnStartup = False
PauseOnLostFocus = False
PauseWhenMinimized = False
AskForExitConfirmationAfterSeconds = 0
AutoLoadSaveState = 0
EnableStateUndo = False
WindowX = {wx}
WindowY = {wy}
WindowWidth = 960
WindowHeight = 600
ShowMenuBar = True
TopMost = False
[CPU]
CPUCore = 1
FastMemoryAccess = True
FunctionReplacements = True
CPUSpeed = 0
[Graphics]
GraphicsBackend = 3 (VULKAN)
FrameSkip = 0
AutoFrameSkip = False
InternalResolution = 2
FrameRate = 0
FrameRate2 = -1
[Sound]
Enable = True
GameVolume = {volume}
[SystemParam]
ButtonPreference = 1
GameLanguage = 1
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default='C:/Program Files/PPSSPP')
    ap.add_argument('--dest', required=True)
    ap.add_argument('--port', type=int, default=60907)
    ap.add_argument('--plugins', action='store_true', help='enable PPSSPP plugins (off by default)')
    ap.add_argument('--volume', type=int, default=0, help='game volume 0..100 (default muted)')
    ap.add_argument('--window', default='40,40', help='window position x,y')
    ap.add_argument('--force-ini', action='store_true', help='rewrite ppsspp.ini if it exists')
    a = ap.parse_args()
    src, dest = Path(a.source), Path(a.dest)
    exe = src / 'PPSSPPWindows64.exe'
    if not exe.is_file():
        raise SystemExit(f'PPSSPP not found: {exe}')
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in SKIP:
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
    if (dest / 'installed.txt').exists():
        raise SystemExit('installed.txt present in destination: instance would not be portable')
    system = dest / 'memstick/PSP/SYSTEM'
    system.mkdir(parents=True, exist_ok=True)
    (dest / 'memstick/PSP/PLUGINS').mkdir(parents=True, exist_ok=True)
    ini = system / 'ppsspp.ini'
    if ini.exists() and not a.force_ini:
        print(f'kept existing {ini} (use --force-ini to rewrite)')
    else:
        wx, wy = (int(v) for v in a.window.split(','))
        ini.write_text(INI.format(port=a.port, plugins='True' if a.plugins else 'False',
                                  volume=a.volume, wx=wx, wy=wy), encoding='utf-8')
        print(f'wrote {ini}')
    print(f'instance ready: {dest / "PPSSPPWindows64.exe"} (debugger port {a.port})')


if __name__ == '__main__':
    main()
