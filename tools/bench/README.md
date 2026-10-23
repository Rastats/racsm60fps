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
| `abc_fire.py` | A/B/C runner: for each config, load the state, apply it, measure (`--rank`, `--weapon` test aids) |
| `move_probe.py` | walk / jump / double jump (`--gaps`) / R + jump trajectories per config, frame-locked scripts, `--angles` scan |
| `move_compare.py` | position difference and heading per 2 vblanks against A0, C-configs shifted one vblank |
| `damage_probe.py` | health and post-hit suppression writes by breakpoint: hit times, HP lost, suppression duration |
| `entities.py` | pump-1 entity positions nearest first; `teleport` test aid |
| `level_route.py` | reach another level from boot: redirects the LEVEL_01 module path in RAM, then presses through the frontend |
| `level_port.py` | ports LEVEL_01 RVAs (C1 core, data addresses, `fixes.DATA`) to another level PRX by masked byte matching, offline |
| `levels.py` | per-level profile keyed by `rcp1` size; `wordfix`, `breakloop`, `clock`, `move_probe`, `fire_rate` use it |
| `board_probe.py` | LEVEL_22 skyboard: speed, steering, jump and race timers per config, times counted from GO |
| `board_compare.py` | board_probe tables: metrics at equal times after GO, gap to A0, timer rates, repeat check |

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

## Other levels (2026-10-22)

```text
python tools/bench/ppsspp_bench.py launch
python tools/bench/level_route.py go --to 02                  # Ryllus, new-game inventory
python tools/bench/states.py save --name banc-ryllus-start
python tools/bench/level_port.py --target LEVEL_02            # what was ported, offline
```

Every level module carries its own engine copy, so each RVA moves. The bench
keeps the hand-checked LEVEL_01 constants and ports them to the resident
level (`levels.py`). A fix whose site is not matched uniquely, or holds
another word, is refused rather than guessed: `C1+crab` on Ryllus fails
with "fixes not ported". Checks against the owner's files: the C1 core of
`cheats/eu/base/LEVEL_02..06,15,22` and the player struct implied by the ten
EU health cheats (Pokitaru to Quadrona) are reproduced exactly.

14. HI16/LO16 relocations of a PRX are relative to the segment they point
    into. An unrelocated `lui`/offset pair aimed at segment 1 (bss) holds
    `rva - segment 1 base`: the LEVEL_01 player pair at 0x30014 reads
    0x5A838 for 0x337940 (segment 1 starts at 0x2DD108).
15. Owned flags do not populate the triangle quick-select ring. The game
    switches weapon when `player+0x99C` (requested id) is nonzero; it copies
    it to `+0x998` (LEVEL_02 code RVA 0x1F2EC). Writing `+0x99C` equips any
    weapon with its model and HUD, owned or not (test aid:
    `fire_rate.request_weapon`, `abc_fire.py --weapon N`; OBSERVED on
    LEVEL_02 only). ShieldCharger (7) and MiniTurret (14) are refused: the
    game falls back to the Blaster, and the ShieldCharger request uses one
    charge.
16. In LEVEL_16-20, `level_port.py` matches the vblank site but not the
    delta, the substep loop or the weapon table, so `levels.py` refuses
    them. The docs already say their substep limit is 1 in the original.
17. LEVEL_15 and LEVEL_21 have the same `rcp1` size (0x3FC700) and differ
    by 14 bytes at image offset 0x235930; their ports are identical, so
    `levels.py` returns one profile named `LEVEL_15/LEVEL_21`. The ISO has
    no LEVEL_11 to LEVEL_14 (the path table names LEVEL_13 and LEVEL_14).
18. The game autosaves on arrival (memstick `SAVEDATA/UCES00420DATA0`), and
    the title screen then resumes that save, which loads the save's level
    entry instead of the LEVEL_01 one. `level_route.py` therefore redirects
    every LEVEL entry and restores them from BOOT.BIN.

## Skyboard (2026-10-23)

```text
python tools/bench/states.py load --name banc-skyboard-arrive       # LEVEL_22, before the countdown
python tools/bench/board_probe.py --state banc-skyboard-arrive --script turn --side 1 -1 \
    --configs A0 C1 --repeat 2 --out <root>/work/runs/<new>
python tools/bench/board_compare.py <root>/work/runs/<new>/board.json
```

Report: [research/live-tests/2026-10-23-skyboard/REPORT.md](../../research/live-tests/2026-10-23-skyboard/REPORT.md).

19. The first frame after a state load is not a fixed emulated instant:
    `states.load` and `--settle` sleep in wall time while emulation runs.
    Scripts that depend on game events (a race start) must be counted
    from the event, not from the first frame. `board_probe.py` counts from
    GO, and C1 reaches GO 2.47 s earlier than A0 because the countdown is a
    frame count.
20. The first frames after a load can move the player (scene reset), which
    looks like a race start. GO is accepted only once the countdown
    (0x22DDCC) is nonzero.
21. The number at the top right of the skyboard HUD is the board speed / 2
    (0x22DC0C), not a timer.
22. A killed BreakLoop script leaves its frame-counter memcheck in PPSSPP:
    the next script times out on `cpu.stepping`. Remove the memcheck
    (`remove_mem_breakpoint(base + frame_counter)`) and resume. During the
    LEVEL_22 race, `buttons(up=True)` did not reach the D-pad double-tap
    detector 0x1056E8 (its state never changed, 2026-10-23); check the pad
    word 0x90F38 before relying on D-pad input there.

LEVEL_22 native fix candidates (`C1+tapwin`, `C1+racecount`,
`C1+boardtimers`, levels.py `NATIVE`) and their first measurements:
[research/live-tests/2026-10-23-skyboard-finish/REPORT.md](../../research/live-tests/2026-10-23-skyboard-finish/REPORT.md).

These belong in `research/GOTCHAS.md` (local research branch) when it is
merged.
