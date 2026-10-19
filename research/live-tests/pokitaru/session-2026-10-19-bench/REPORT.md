---
kind: live
title: "Unattended A/B/C bench: Blaster cadence A0 vs C1 vs C1+weapondt in emulated time"
date: 2026-10-19
authors: ["Claude (Opus 5.5)"]
status: complete
evidence: [OBSERVED, TESTED, UNKNOWN]
summary: "First owner-free measurement: from one savestate, C1 halves the Blaster cadence (1.998 -> 0.983 shots/s) and C1+weapondt restores it to A0 to the frame, held or tapped; the first shot comes one game frame after the press in every config."
systems: [Blaster, weapons, timing, tooling]
levels: [Pokitaru]
variants: [A0, C1, C1+weapondt]
environment: "PPSSPP 1.20.4 portable, Direct3D 11, JIT, plugins off, no InterpGate; CPU 222 MHz; window in background"
supersedes: []
related: [docs/WEAPONS_PARITY_2026-10-02.md, tools/bench/README.md]
---

# Unattended A/B/C bench: Blaster cadence

## Question

Can an agent reproduce a published A/B/C result with nobody at the keyboard,
using emulated time instead of wall time?

## Setup

- ISO UCES00420. LEVEL_01.PRX sha256 `d10a81d076fb44987a45314a020cda2f7e8b39f860b957911ca9365464676571`,
  which equals the value recorded in the repo.
- A fresh PPSSPP 1.20.4 portable instance. The game was started from a new
  save: language, New Game, intro skipped, all driven by `tools/bench/`. The
  level is Pokitaru, `rcp1` at `0x09139D00`, size `0x46B900`.
- Savestate `pokitaru-blaster`: start of the level, Blaster (weapon id 2)
  drawn, ammo stock 60. The state is local, not committed.
- Configurations, applied by `tools/bench/wordfix.py` after each state load:
  - A0 is the original game.
  - C1 is the three-word core (`0x96650`, `0x151E0`, `0x2FCFC`).
  - C1+weapondt adds delay slot `0x2FCF4`, `mov.s f12,f20` → `add.s f12,f20,f20`,
    plus a JIT refresh of the preceding branch.
- Measurement by `tools/bench/fire_rate.py` on `tools/bench/breakloop.py`.
  Input is frame-locked: the press happens at a game frame boundary (frame
  counter write break) and is the time origin. Fire input lasts 6 emulated
  seconds, either held or tapped (2 vblanks pressed, 2 released, which is
  the fastest tap A0 can see: one frame down, one frame up). A write
  breakpoint on the stock (`module + 0x2AEA4C`) timestamps every shot with
  CoreTiming ticks; seconds = ticks / 222e6.

## Results (OBSERVED; runs `work/runs/abc-fire-004-hold`, `abc-fire-004-tap2`)

Shots within 6 s and refire interval:

| Config | Hold: shots, gap | Tap: shots, gap |
|---|---|---|
| A0 | 12, 0.5005 s (15 frames) | 12, 0.5339 s (16 frames) |
| C1 | 6, 1.0177 s | 6, 1.0177 s |
| C1+weapondt | 12, 0.5005 s | 12, 0.5339 s |

Shots per second (from first to last shot): hold 1.998 / 0.983 / 1.998,
tap 1.873 / 0.970 / 1.873. First shot after the press: 2.03 vblanks in A0
(one 30 Hz frame) and 1.03 vblanks in C1 and C1+weapondt (one 60 Hz frame),
in both modes. Stock before and after matches the counted shots (no shot
left out of the window). The gaps equal those of the earlier run
`abc-fire-002` (two repeats, identical).

## Interpretation

- **TESTED:** C1 halves the Blaster refire in this setup (ratio 2.03), and
  `weapondt` restores it to A0 to the frame, held or tapped. This reproduces
  the published outcome (`docs/WEAPONS_PARITY_2026-10-02.md`: weapondt
  cadence = A0).
- **OBSERVED:** the press-to-shot latency is one game frame in every config,
  so C1+weapondt answers one vblank (16.7 ms) sooner than A0. This is the
  expected effect of a 60 Hz input sample, not a timing defect (INFERRED).
- **UNKNOWN:** the absolute cadence differs. The published A0 value is 4.134
  shots/s; here it is 1.998 held and 1.873 at the fastest tap, so the input
  method does not explain it. Remaining cause, unverified: the game state
  (the published runs used a later save; a higher weapon level or another
  upgrade may fire faster). To settle with the owner.

## Weapon rank (test aid; run `work/runs/abc-fire-005-rank3` and a scan)

The savestate holds the Blaster at rank 0 (V1), XP 0, no mod, in both
inventory copies. Writing the rank in the level copy (`--rank`, RAM only,
layout from `tools/runtime/inventory-aid.py`) changes the cadence at once:

| Rank | A0 gap (frames), shots/s | C1 shots/s | C1+weapondt |
|---|---|---|---|
| 0, 1, 2 | 15, 1.998 | 0.983 | = A0 |
| 3, 4, 5, 6, 7 | 8, 3.746 | 1.998 | = A0 (rank 3) |

Ranks 4 to 7 were measured in A0 only; C1 at ranks 1, 3, 5, 7. The C1 gap
is 61 C1 frames at ranks 0-2 and 30 at ranks 3+, so uncorrected 60 FPS does
not simply double the interval. `weapondt` gives A0 to the frame at both
ranks tested. **UNKNOWN:** no rank gives the published 4.134 shots/s (or
the published C1 1.842). Mods, or the wall-clock method of the published
runs, remain possible; the owner's save would settle it.

## Correction (2026-10-19, same session)

A first version of `fire_rate.py` read the stock at the break. A write
breakpoint stops before the store, so each shot was credited to the next
break and the first shot was missed. Its gaps and cadence were right; its
first-shot delays (0.5177 s A0, 1.0349 s C1) were one refire interval too
long, and the claim drawn from them ("draw-to-fire path corrected") is
withdrawn. The values above come from the fixed tool.

## Method notes

- Emulated time removes the foreground requirement. The window stayed in the
  background for the whole run.
- Polling was abandoned: back-to-back requests froze CoreTiming.
- Write breakpoints stop before the store; a store in a delay slot stops on
  its branch. Both are handled in `breakloop.py` (`tools/bench/README.md`,
  pitfalls 8 and 9).
- Raw JSON stays local (`<root>/work/runs/`).
