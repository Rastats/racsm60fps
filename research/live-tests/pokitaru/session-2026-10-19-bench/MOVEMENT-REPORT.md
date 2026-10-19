---
kind: live
title: "Unattended movement A/B: walk, jump and running jump, A0 vs C1, frame-locked input"
date: 2026-10-19
authors: ["Claude (Opus 5.5)"]
status: complete
evidence: [OBSERVED, TESTED, INFERRED]
summary: "With the three-word C1 core, Ratchet's walk and jump trajectories equal A0 shifted by exactly one vblank (max deviation 0.0005 u walking, 0.0000 u jumping); a 0.03 u landing transient on a slope is the only residual seen."
systems: [player, movement, timing, tooling]
levels: [Pokitaru]
variants: [A0, C1]
environment: "PPSSPP 1.20.4 portable, Direct3D 11, JIT, plugins off, no InterpGate; CPU 222 MHz; window in background"
supersedes: []
related: [research/v2/pokitaru/player-clock-socle-map.md, tools/bench/README.md, research/live-tests/pokitaru/session-2026-10-19-bench/REPORT.md]
---

# Unattended movement A/B: walk and jump

## Summary

- C1 (three-word core) moves Ratchet exactly like A0, one vblank earlier.
- Walking: same top speed, 6.000 units/s in both, same final position
  (10.662 u), max deviation 0.0005 u once C1 is shifted by one vblank.
- Standing jump: same arc, apex 1.12 u, max deviation 0.0000 u after the
  same one-vblank shift.
- Running jump: horizontal path identical (0.0005 u); vertical deviation up
  to 0.030 u for about 6 vblanks after landing on a slope.
- The one-vblank lead is the 60 Hz input sample, not a timing defect
  (INFERRED): C1 starts, jumps and stops one vblank sooner.

## Setup

- Same ISO, module hash and savestate as the fire-rate report
  (`pokitaru-blaster`: Pokitaru start, Blaster drawn).
- Tool: `tools/bench/move_probe.py`. Input is frame-locked
  (`breakloop.py`): the script is written in vblanks from the first frame
  boundary, so A0 (2 vblanks per frame) and C1 (1 per frame) get the same
  input at the same emulated instants.
- Position: player `module+0x337940`, vector `+0x30/+0x34/+0x38`. The static
  map (`research/v2/pokitaru/player-clock-socle-map.md`) labelled it
  INFERRED; live check here: `+0x30` and `+0x38` change while walking on
  flat ground, `+0x34` rises during a jump. `+0x34` is the vertical axis.
- Samples: one per game frame, at the frame counter write (30 Hz in A0,
  60 Hz in C1). Comparisons use even vblank indices, present in both.
- Scripts: `walk` = stick held 120 vblanks (2.0 s) then neutral to 180;
  `jump` = cross held 4 vblanks; `walkjump` = stick held 180 vblanks, cross
  for 4 vblanks at vblank 60. Stick direction 180° (down): the open path
  found by scanning 8 directions in A0 (0° hits an obstacle after 1.2 s).

## Results (OBSERVED)

| Test | Metric | A0 | C1 |
|---|---|---|---|
| walk | path at 1.0 s / 2.0 s (u) | 4.443 / 10.443 | 4.544 / 10.543 |
| walk | top speed, 1.0-2.0 s (u/s) | 6.000 | 6.000 |
| walk | glide after release (u) | 0.26 | 0.16 |
| walk | final displacement (u) | 10.662 | 10.662 |
| jump | apex above start (u) | 1.118 | 1.120 |
| jump | airborne / landed (vblank) | 4 / 32 | 3 / 30 |

A0 is sampled every second vblank, which explains the apex and landing
differences in the jump row (C1 sees the in-between frames).

Shifted comparison: A0 at vblank v against C1 at v - k, all even v
(`move-walk-003-a180`, `move-jump-001`, `move-walkjump-001`):

| Test, axis | k = 0 | k = 1 | k = 2 |
|---|---|---|---|
| walk, path | 0.1005 | **0.0005** | 0.0995 |
| walk, height | 0.0232 | **0.0013** | 0.0342 |
| jump, height | 0.1460 | **0.0000** | 0.1580 |
| running jump, path | — | **0.0005** | — |
| running jump, height | — | **0.0298** | — |

Max absolute difference in game units; 76 to 91 points per test. Walk runs
were repeated twice with identical results (deterministic).

## Interpretation

- **TESTED:** for walking and jumping at this location, C1 already gives
  A0 trajectories; no movement fix is needed for these two actions. This is
  consistent with the substep design: A0 runs 2 player substeps per 30 Hz
  frame and C1 runs 1 per 60 Hz frame, 60 substeps per second in both.
- **INFERRED:** the one-vblank lead (0.1 u at 6 u/s) comes from input being
  read every 60 Hz frame instead of every 30 Hz frame. It cancels over a
  full move: C1 also stops one vblank sooner, hence the equal final position.
- **OBSERVED, small residual:** after the running jump, the height differs
  by up to 0.030 u at landing on sloped ground (A0 v=98: 0.162 u above
  start), decaying over about 6 vblanks. Candidate: a per-frame smoothing or
  ground snap. Not visible at this size by expectation, untested visually.

## Limits

- One location, flat-to-sloped ground, no enemies, no ledges or water.
- Not covered: double jump, long jump, wall jump, swinging, grind, damage
  knockback, camera. The same probe can take more scripts.
- The trajectory compares player position only; animation and camera need
  their own observers.

## Method notes

- Diagonal stick inputs at full deflection barely move Ratchet here (0.7 to
  1.1 u in 2 s) while cardinal ones walk at 6 u/s; cause UNKNOWN (input
  mapping or turning), irrelevant to the A/B comparison.
- Raw trajectories stay local (`<root>/work/runs/move-*`).
