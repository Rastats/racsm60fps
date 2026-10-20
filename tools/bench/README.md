# Autonomous test bench (PPSSPP)

Status: working, 2026-10-19. First unattended A/B/C measurement reproduced
(report: [research/live-tests/pokitaru/session-2026-10-19-bench/REPORT.md](../../research/live-tests/pokitaru/session-2026-10-19-bench/REPORT.md)).
2026-10-20: double jump, R + jump and the camera fix measured; damage and
elevator blocked on locating a crab and the elevator
([session-2026-10-20-bench/REPORT.md](../../research/live-tests/pokitaru/session-2026-10-20-bench/REPORT.md)).

Goal: let an agent run PPSSPP instances, look at the screen, drive the
controller, apply fixes and measure A0 / C1 / C candidates **without the owner
at the keyboard and without depending on host speed**. The read-only observers
in `tools/runtime/` stay as they are; this folder adds the control layer.

## Layout on disk (outside Git)

| Path | Contents |
| --- | --- |
| `<root>/game/UCES00420.iso` | the owner's ISO (sha256 of LEVEL_01.PRX `d10a81d0…6571`, matches the repo records) |
| `<root>/game/iso/PSP_GAME/...` | modules extracted with `tools/env/iso_extract.py` (all PRX are plain ELF; EBOOT.BIN is encrypted, BOOT.BIN is the plain copy) |
| `<root>/emu/ppsspp-1/` | portable PPSSPP 1.20.4 instance (`tools/env/setup_ppsspp_portable.py`) |
| `<root>/work/states/*.ppst` | named savestates |
| `<root>/work/runs/<run>/` | raw results (JSON), never committed |

`<root>` defaults to `D:/racsm60fps` (`RACSM_ROOT` overrides it). `fixes.py`
also needs the clean module at
`01-Travail-et-profil-PPSSPP/Overcompensated-Reprise-2026-09-14/development-v0.6.3-generalisation/prx-reference/LEVEL_01.PRX`
(gitignored): several fix families read their original words from it.

## Setup

```text
python tools/env/iso_extract.py <iso> --out <root>/game/iso --only PSP_GAME/USRDIR/BIN
python tools/env/setup_ppsspp_portable.py --dest <root>/emu/ppsspp-1 --port 60907
```

The instance is portable because `installed.txt` is absent, so the owner's
`Documents/PPSSPP` configuration is never touched. Its ini enables the
debugger on port 60907, disables plugins and cheats, mutes the game and uses
Direct3D 11. The graphics backend does not change game logic.

## Tools

| Tool | What it does |
| --- | --- |
| `ppsspp_bench.py` | debugger client and CLI: `launch`, `status`, `modules`, `shot`, `press`, `hold`, `stick`, `read`, `pause`, `resume`, `quit` |
| `wincap.py` | window capture (PrintWindow); the default for `shot` |
| `states.py` | named savestates: `save --name X`, `load --name X`, `list` |
| `advance_to_level.py` | presses through dialogs and cutscenes until a level module (by `rcp1` size) is resident |
| `clock.py` | ticks per game frame, so the emulated frame rate and the CPU clock |
| `wordfix.py` | applies the C1 core and any word-level fix of `tools/runtime/fixes.py` (`DATA`) without a plugin |
| `breakloop.py` | event loop: exact tick and new value of watched stores, plus a per-frame callback for frame-locked input |
| `fire_rate.py` | fire cadence and first-shot latency in emulated time (`--mode hold` or `tap`) |
| `abc_fire.py` | A/B/C runner: for each config, load the state, apply it, measure (`--rank` test aid) |
| `move_probe.py` | walk / jump / double jump (`--gaps`) / R + jump trajectories per config, frame-locked scripts, `--angles` scan |
| `move_compare.py` | position difference and heading per 2 vblanks against A0, C-configs shifted one vblank |
| `damage_probe.py` | health and post-hit suppression writes by breakpoint: hit times, HP lost, suppression duration |
| `entities.py` | pump-1 entity positions nearest first; `teleport` test aid |

Typical session:

```text
python tools/bench/ppsspp_bench.py launch
python tools/bench/advance_to_level.py --size 0x46B900        # Pokitaru
python tools/bench/states.py save --name pokitaru-blaster
python tools/bench/abc_fire.py --state pokitaru-blaster --configs A0 C1 C1+weapondt --repeat 2 --out <root>/work/runs/<new>
python tools/bench/ppsspp_bench.py quit                        # stops only this instance's PID
```

## Time base

- `cpu.status.ticks` is PPSSPP CoreTiming: emulated CPU cycles. It does not
  depend on host speed, window focus or throttling.
- The CPU clock is **222 MHz** in this game. Measured: in A0, 1,818,521,757
  ticks over 245 game frames gives 2.004 vblanks per frame. In C1, frames are
  exactly 3,703,700 ticks, which is one 59.94 Hz vblank at 222 MHz (`clock.py`,
  2026-10-19, Pokitaru start, OBSERVED).
- A0 therefore runs at 29.97 frames per emulated second (two vblanks per
  frame). C1 runs at 59.94 with no dropped frame at the Pokitaru start.

## Sampling: breakpoints, not polling

Back-to-back debugger requests starve the emulator: ticks stopped advancing
while a polling loop ran (OBSERVED, and also noted in
`docs/WEAPONS_PARITY_2026-10-02.md`). Events are timestamped with
breakpoints instead. The CPU stops at the event, the `cpu.stepping` broadcast
carries `ticks`, the script reads what it needs and resumes. Emulated time
is frozen while stepping, so samples are exact even if the host is slow.

`breakloop.py` puts a write breakpoint (with `change`) on each watched word
and on the game frame counter (RVA `0x2AF28C`). A write breakpoint stops
**before** the store, so the loop decodes the store and reads its source
register to get the new value. The frame counter break is the frame
boundary: input sent there applies to a known frame, never to a wall-clock
moment. Tap patterns are counted in vblanks, so they mean the same input in
A0 (2 vblanks per frame) and C1 (1 vblank per frame).

## Pitfalls found while building the bench (2026-10-19)

1. `gpu.buffer.screenshot` and `renderColor` answer "Could not download
   output" on 1.20.4 with both Vulkan and D3D11, even with the CPU stepping.
   The workaround is a PrintWindow capture of the window (`wincap.py`, works
   when the window is covered, not when it is minimized).
2. `cpu.stepping` and `cpu.resume` are acknowledged by an untagged broadcast
   of the same name, not by a reply carrying the request ticket.
3. 1.20.4 has no savestate request in the debugger API. The window menu
   commands (WM_COMMAND, IDs from `Windows/resource.h` at tag v1.20.4) work
   without focus. Boot-time loading also exists:
   `PPSSPPWindows64.exe --state=<file> <iso>`.
4. Savestates freeze the equipped weapon: the first state held the wrench
   (id 1), and the first circle press only draws the Blaster (id 2). Make
   states with the weapon under test already drawn.
5. A script killed while holding a button leaves it pressed, which emptied
   the Blaster stock. Runs now start with `release_all()`.
6. The debugger web server listens on all interfaces without authentication.
   Every 9 minutes it also sends the machine's LAN address and port to
   report.ppsspp.org, so the official web UI can find it (PPSSPP sources,
   `Core/WebServer.cpp`). Deny the firewall prompt for the copied executable:
   local clients work either way. `RemoteDebuggerLocal` only selects a
   locally hosted UI.
7. A failed multi-word patch must not leave a partial state. `wordfix.py`
   checks every guard first, then writes, and rolls back on error.
8. A write memcheck stops before the store executes: PC is on the store and
   memory still holds the old value. The first version of `fire_rate.py`
   read memory at the break, so it credited each shot to the next break and
   missed the first one. Cadence from gaps was right; the first-shot delay
   was one refire interval too long (fixed 2026-10-19, `breakloop.py`).
9. A store in a branch delay slot stops the CPU on the branch, not on the
   store (the frame counter increment sits in the slot of a `jal`).
   `pending_store()` decodes the slot when PC holds a branch.

10. `wordfix.apply()` skipped fix names missing from `DATA` without a word
    until 2026-10-20, so `C1+camera` ran as plain C1. It now expands
    `camera` and the `fixes.py` aliases and refuses anything else.
11. Path length hides heading errors: compare positions at equal emulated
    times (`move_compare.py`). The 2026-10-19 walk parity of 0.0005 u was a
    path-length figure; positions differ by 0.008 u.
12. Callback RVAs near a class's known functions are not proof of the class:
    on 2026-10-20 the guessed crab group was the Gadgetron vendor. Check by
    `entities.py teleport` and a window capture before measuring.
13. Init-time fixes need a state taken before the init. `elevator` rewrites
    the Lvl3Elevator initializer (`docs/FIX_CATALOGUE_2026-10-01.md`): applied
    by `wordfix.py` after loading a state where the elevator already exists,
    it changes nothing and `C1+elevator` measures plain C1.

These belong in `research/GOTCHAS.md` (local research branch) when it is
merged.
