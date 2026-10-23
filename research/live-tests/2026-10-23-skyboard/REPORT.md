---
kind: live
title: "Kalidon skyboard (LEVEL_22) A0 / C1: speed and steering within 3 %, every race timer counted in frames runs twice as fast in C1"
date: 2026-10-23
authors: ["Claude (Opus 5.5)"]
status: partial
evidence: [OBSERVED, INFERRED, UNKNOWN]
systems: [skyboard, movement, race-timers, hud, tooling]
levels: [Kalidon Skyboard]
variants: [A0, C1]
environment: "PPSSPP 1.20.4 portable (instance ppsspp-1, port 60907), Direct3D 11, JIT, plugins off; CPU 222 MHz; window in background; no other PPSSPP instance running"
supersedes: []
related: [research/live-tests/2026-10-22-coverage/REPORT.md, research/v2/damage-followup-20261006/SKYBOARD.md, research/v2/damage-atlas-20261006/CLANK_MINIGAMES.md, tools/bench/README.md]
summary: "From banc-skyboard-arrive, with every time counted from GO: board speed in C1 is 2.6 % lower 0.5 s after GO and within 0.3 % from 2 s on, with or without boost; steering turns the same angle (-1.0 % over 1 s of full stick) but recentres faster after release. The pre-race countdown lasts 4.97 s in A0 and 2.50 s in C1, and the race frame counter (written in the RaceController code) counts 60 per second instead of 30. A third timer runs at half speed in C1."
state: "banc-skyboard-arrive (LEVEL_22, ship arrival before the race countdown)"
---

# Kalidon skyboard, 2026-10-23: A0 against C1

Five-line summary:

- Speed matches A0 within 3 %. C1 is 2.6 % slower 0.5 s after GO, then
  within 0.3 % from 2 s, with or without boost.
- Steering matches A0: 1 s of full stick turns the board 102.1 degrees in A0
  and 101.0 in C1. After the stick is released, C1 recentres faster (at
  +10 vblanks: 9 degrees in A0, 36 in C1). Cause UNKNOWN.
- Everything counted in frames runs twice as fast in C1. The pre-race
  countdown lasts 4.97 s in A0 and 2.50 s in C1. The race frame counter,
  written by the race controller code, counts 60 per second instead of 30.
- A delta timer stepped once per substep runs at half speed in C1. Its
  meaning is UNKNOWN.
- Every A0 / C1 run was repeated twice with bit-identical samples after GO.
  The control-mapping runs were done once, in A0.

## Method

Same bench as 2026-10-19/22 (`tools/bench/README.md`). New tool:
`tools/bench/board_probe.py`, with `board_compare.py` for the tables.

- **GO.** Every time is counted from GO, the last still frame before the
  board moves. It is accepted only once the pre-race countdown is running.
  The first frames after a state load can move the player too (scene reset),
  and they gave a false GO in the first runs.
- **Why not from the first frame.** Loading a state leaves a wall-clock
  settle while emulation runs, so the first sampled frame is a different
  emulated instant in each run. C1 also counts the countdown twice as fast.
  A script counted from the first frame therefore hits a different point of
  the track in each config: the countdown starts at vblank 66 in one A0 run
  and at vblank 24 in a C1 run.
- **Instants.** Values are compared at equal emulated times after GO, with
  positions interpolated linearly between frame samples (A0 30 Hz, C1 60 Hz).
  Speed comes from the position 4 vblanks before and after each instant.
  Heading is the direction of the velocity, `atan2(dx, dz)`.
- **Inputs.** Inputs are frame-locked (`breakloop.py`) and counted in vblanks
  after GO. Nothing is pressed before GO.
- **Scripts.** All last 300 vblanks (5 s) after GO:
  - `straight`: no input;
  - `button`: one button held from 60 to 180;
  - `turn`: stick full right or left from 60 to 120.

### Words found (LEVEL_22 module RVAs, OBSERVED)

Found by RAM scans (values that track emulated time across paused dumps of the
whole user RAM) and, for the HUD, by matching the displayed number. Writers
come from write breakpoints (`writes` = stores per game frame).

| Word | RVA, type | Writer, behaviour |
| --- | --- | --- |
| HUD number (top right) | 0x22DC0C float | PC 0x92F88; 2 writes per frame in A0, 1 in C1; equals board speed / 2 |
| Countdown | 0x22DDCC int | PC 0x95988, -1 per frame; set to 135 before GO and to 180 at GO (PC 0x955AC) |
| Race frames | 0x240658 int | PC 0x1057F4 (called from 0x105710), +1 per frame from GO |
| Clock 227D04 | 0x227D04 float | PC 0x7BAE8, +1/30 per frame (constant step) |
| Timer 29E588 | 0x29E588 float | PC 0x28B58 (called from 0x30020), -delta per write; 2 writes per frame in A0, 1 in C1 |
| Player + 0x574 | 0x29E0F4 float | PC 0x2C494, +delta once per frame |

The HUD number matched these values: 10.0625, 10.3575 and 14.9775 in memory,
against 10.06, 10.39 and 15.32 on screen. The capture shows the previous
frame, so the last value lags during a boost. At the instants checked
(straight run, 0.5, 3.0 and 4.0 s, both configs) it is 0.500 to 0.502 times
the speed from positions.

The race frame writer, 0x1057F4, lies just after the RaceController update at
0x104E34 (`CLANK_MINIGAMES.md` § 7). Whether that update owns the writer is
INFERRED from proximity. A full scan of user RAM (0x08800000-0x0A000000) found
no race time stored in seconds that starts at GO.

## Results

All OBSERVED. Each A0 / C1 run was repeated twice, and the post-GO samples
(positions and words) were identical bit for bit between repeats. The
control-mapping runs (Controls below) were done once, in A0.

GO resolution: GO is the last still frame. In A0 that frame is 2 vblanks
before the first moving one, in C1 1 vblank, so GO in A0 can sit up to one
vblank earlier relative to the true start of motion. That is about 0.37 u
of travel at 22 u/s. The distance rows below are uncertain by that much (the
-0.36 u at 0.5 s may be entirely this offset). Speed rows are not affected: a
one-vblank shift changes speed by about 0.03 u/s.

### Speed

| Metric | A0 | C1 | Gap |
| --- | --- | --- | --- |
| Speed 0.5 s after GO, no input (u/s) | 22.47 | 21.88 | -2.6 % |
| Speed 1.0 s | 21.49 | 21.12 | -1.7 % |
| Speed 2.0 s | 20.53 | 20.40 | -0.7 % |
| Speed 3.0 s | 20.18 | 20.13 | -0.2 % |
| Distance 3.0 s after GO (u) | 62.61 | 61.69 | -1.5 % |
| Distance 4.9 s | 102.16 | 99.77 | -2.3 % |
| Boost (square, held 1-3 s): speed 2.0 s | 26.77 | 26.70 | -0.3 % |
| Boost: speed 3.0 s | 28.80 | 28.77 | -0.1 % |
| Boost: distance 3.0 s | 73.78 | 73.01 | -1.0 % |

- Without boost, cruise speed settles near 20 u/s in both configs. The
  C1 deficit is concentrated in the first second after GO.
- The distance gap at 4.9 s also includes the trajectory: the two configs
  take the first bend on slightly different lines (heading below).
- With boost, A0 hits an obstacle and stops before 4.9 s, but C1 does not:
  at 4.9 s A0 is at 0 u/s and C1 at 33.9 u/s. One input sequence therefore
  gives a different race outcome.

### Steering

Heading change from the stick press (60 vblanks after GO):

| Metric | A0 | C1 | Gap |
| --- | --- | --- | --- |
| Heading 60 vblanks after GO, no input | 163.25 deg | 164.88 deg | +1.63 deg |
| Left, +10 vblanks (v70) | +15.56 deg | +17.73 deg | +2.17 deg |
| Left, +40 (v100) | +75.84 deg | +74.99 deg | -1.1 % |
| Left, +60 (v120, release) | +102.06 deg | +100.99 deg | -1.0 % |
| Left, +10 after release (v130) | +92.72 deg | +65.37 deg | -27.4 deg |
| Right, +10 (v70) | -12.91 deg | -14.60 deg | +1.69 deg |
| Right, +40 (v100) | -66.02 deg | -67.97 deg | +3.0 % |

- **Stick held.** The board turns the same angle while the stick is held.
  The first 10 vblanks differ by about 2 degrees. A0 samples every second
  vblank, so the input lands up to one vblank later there, which makes up
  most of that onset gap.
- **Right turn.** From about v110 the right turn runs into the track side in
  both configs (speed 0 at 3.0 s). Only the left turn is clean after release.
- **After release.** C1 swings back toward the track direction faster: -9.3
  degrees in A0 and -35.6 in C1 during the first 10 vblanks after release.
  At v150 the heading is +10.5 degrees in A0 and -1.7 in C1, relative to v60.
  INFERRED: a heading or alignment smoothing step that converges per call
  runs twice as often in C1. This matches the walk ±90 degree overshoot of
  2026-10-22. It is not proven for the board.
- **No input.** The C1 heading is 1.6 degrees higher (`atan2(dx, dz)`)
  from GO on.

### Jump (cross, held 60 to 180)

| Metric | A0 | C1 | Gap |
| --- | --- | --- | --- |
| Apex above the no-input line (u) | 3.139 | 3.148 | +0.3 % |
| Apex time after GO | v100 | v100 | 0 |

Airtime is not given: after the jump both trajectories leave the no-input line
for the rest of the window, so landing cannot be read from the height
difference.

### Timers (rate per emulated second, 0.5 to 4.9 s after GO)

| Timer | A0 | C1 | Gap |
| --- | --- | --- | --- |
| Countdown start to GO (s) | 4.9716 | 2.5025 | -49.7 % |
| Countdown after GO, 180 frames (s) | 6.0 | 3.0 | -50 % |
| Race frames | 30.0 /s | 60.0 /s | x2 |
| Clock 227D04 | 0.999 /s | 1.998 /s | x2 |
| Timer 29E588 | -1.998 /s | -0.999 /s | x0.5 |
| Player + 0x574 | 0.999 /s | 0.999 /s | 0 |

- **Race frames.** If the game shows race or lap times from this counter at
  30 per second, C1 times come out doubled. This is INFERRED: no race was
  finished here, so no time screen was read.
- **Countdown.** The countdown, and the 180-frame window that follows GO, are
  frame counts, so C1 starts the race 2.47 s early. From countdown start to
  GO is 298 vblanks in A0 and 150 in C1, so 149 and 150 game frames: 135 at
  -1 per frame, then 14 to 15 frames to GO.
- **Clock 227D04.** It adds a constant 1/30 per frame, the same pattern as
  the mine age of `SKYBOARD.md` (literal 1/30 at EC22C).
- **Timer 29E588.**
  - It takes the frame delta once per substep: two substeps per frame in A0,
    each with 1/30, and one in C1 with 1/60.
  - In A0 it therefore falls 2 per emulated second, and in C1 1 per second.
  - Its meaning is UNKNOWN. A0 is the reference, so C1 runs it at half speed.
- **HUD speed.** It is written once per substep too. It matches the
  position-derived speed in both configs, so the display is right.

### Controls (A0, `button` script)

| Button | Effect |
| --- | --- |
| square | boost: 21.55 u/s at the press (1.0 s after GO), 28.80 u/s at 3.0 s, HUD 14.4 |
| circle | identical to square, sample for sample |
| cross | jump |
| R | no measurable effect (identical to no input) |

## Not measured

- **Race result.** Race and lap times at the finish, rank and race
  penalties: no race was finished.
- **Mines.** No mine contact (`SKYBOARD.md` protocol).
- **Fixes.** No C1 fix was tried on the board. Whether one of the 95 fixes
  ported to LEVEL_22 targets the six writers above was not checked.
- **Boost meter.** The boost meter (right-hand bar) was not located.

## Questions for Linkinito

Kept apart: they are relayed by Antoine, never sent from here.

1. Does his LEVEL_22 patch handle the race frame counter (0x240658) and the
   countdown (0x22DDCC)? Do race times use the frame counter at 30 per second?
2. What is the float at 0x29E588? It takes the delta once per substep, so it
   runs at half speed in C1.
3. After a turn, the board recentres faster in C1. Which routine aligns the
   board heading?

## Files

- Tools:
  - `tools/bench/board_probe.py` (new);
  - `tools/bench/board_compare.py` (new);
  - `tools/bench/breakloop.py`: a frame callback may now end a run by
    returning True;
  - `tools/bench/README.md`: pitfalls 19-21.
- Raw results (not committed), under `<root>/work/runs/`:
  - `banc-sky-straight-002`, `banc-sky-boost-001`, `banc-sky-jump-001`,
    `banc-sky-turn-001`, `banc-sky-button-{cross,square,rtrigger}`,
    `banc-sky-button-circle-2`, each with `board.json` and most with
    `compare.json`;
  - scans and writers in `banc-sky/` (`scanram-A0/C1.json`, `hud-a0/`,
    `writers-A0/C1.json`).
- Scripts used for the scans, writers, turn and jump tables (not committed),
  in `<root>/work/runs/banc-sky/scripts/`:
  - `scan.py` (RAM scan), `hudscan.py` (HUD match), `writers.py` (writer PCs);
  - `explore.py`, `turn.py`, `jump.py`, `montage.py`, `peek.py`.
