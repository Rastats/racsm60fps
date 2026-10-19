---
kind: live
title: "Unattended A/B/C bench: Blaster cadence A0 vs C1 vs C1+weapondt in emulated time"
date: 2026-10-19
authors: ["Claude (Opus 5.5)"]
status: complete
evidence: [OBSERVED, TESTED, UNKNOWN]
summary: "First owner-free measurement: from one savestate, C1 halves the Blaster cadence (1.998 -> 0.983 shots/s) and C1+weapondt restores it to A0 to the frame; repeat identical."
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
- Measurement by `tools/bench/fire_rate.py`. Circle is held for 6 emulated
  seconds. A write breakpoint on the stock (`module + 0x2AEA4C`) timestamps
  every shot with CoreTiming ticks; seconds = ticks / 222e6.

## Results (OBSERVED; run `work/runs/abc-fire-002`, two repeats)

| Config | Shots in 6 s | Shots/s | Median gap | First shot after press |
|---|---|---|---|---|
| A0 | 12 | 1.998 | 0.5005 s (15.00 A0 frames) | 0.5177 s |
| C1 | 5 | 0.983 | 1.0177 s | 1.0349 s |
| C1+weapondt | 12 | 1.998 | 0.5005 s | 0.5177 / 0.5174 s |

Both repeats gave identical counts and gaps.

## Interpretation

- **TESTED:** C1 halves the Blaster refire in this setup (ratio 2.03), and
  `weapondt` restores it to A0 to the frame. This reproduces the published
  outcome (`docs/WEAPONS_PARITY_2026-10-02.md`: weapondt cadence = A0).
- **UNKNOWN:** the absolute cadence differs. The published A0 value is 4.134
  shots/s; here it is 1.998. Likely causes, unverified: a different game
  state (the published runs used a later save, with more weapons and possibly
  a weapon level or mod that fires faster), or held input versus repeated
  presses. To settle with the owner (question list in the session handoff).
- The first-shot delay also matches A0 under weapondt, so the draw-to-fire
  path is corrected too, at this location.

## Method notes

- Emulated time removes the foreground requirement. The window stayed in the
  background for the whole run.
- Polling was abandoned: back-to-back requests froze CoreTiming.
- Raw JSON stays local (`<root>/work/runs/`).
