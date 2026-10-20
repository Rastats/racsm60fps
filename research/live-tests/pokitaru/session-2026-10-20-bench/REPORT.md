---
kind: live
title: "Unattended movement and damage A/B: double jump, R + jump (camera), damage and elevator attempts"
date: 2026-10-20
authors: ["Claude (Opus 5.5)"]
status: partial
evidence: [OBSERVED, INFERRED, UNKNOWN]
systems: [player, movement, camera, damage, tooling]
levels: [Pokitaru]
variants: [A0, C1, C1+camera]
environment: "PPSSPP 1.20.4 portable, Direct3D 11, JIT, plugins off, no InterpGate; CPU 222 MHz; window in background"
supersedes: []
related: [research/live-tests/pokitaru/session-2026-10-19-bench/MOVEMENT-REPORT.md, tools/bench/README.md, tools/runtime/fixes.py]
summary: "Double jump: C1 equals A0 shifted by one vblank (0.0000 u) for second presses 8 to 32 vblanks after the first. Holding R (manual camera yaw) while running turns Ratchet's heading 2.1x as far in C1; the `camera` fix restores the final heading. Slope walking matches at the same spot (0.001 u). Damage and elevator tests are blocked: no crab or elevator located."
state: pokitaru-blaster (Blaster drawn, start of Pokitaru)
---

# Pokitaru bench, 2026-10-20: double jump, R + jump, damage and elevator attempts

## Summary

- **Double jump, OBSERVED.** C1 reproduces A0 exactly once shifted by one
  vblank, with a max position difference of 0.0000 u. This holds for second
  presses 8, 16, 24 and 32 vblanks after the first. Both configs double-jump
  at 8, 16 and 24 and neither does at 32 (apex = single jump), so the window
  closes between 24 and 32 vblanks in both.
- **R + jump while running, OBSERVED.** C1 diverges by up to 2.99 u from A0.
  - The cause is heading. R is the manual camera yaw (`tools/runtime/fixes.py`,
    `camera`: "manual yaw/pitch (L/R, D-pad) ... per-call steps: 1/30").
  - The stick is camera-relative, so Ratchet turns with the camera. In A0 he
    turns −25.6° (from −127.6° to −153.2°); in C1 he turns −53.7°, 2.1 times
    as much.
  - **C1+camera** restores the final heading (−153.15° at v134, the same as
    A0). The turn starts about one A0 frame earlier.
- **Slope speed after landing: no residual, OBSERVED.**
  - In `move-longjump-002-camera`, C1+camera covered 9-15 % more distance than
    A0 per 2 vblanks after landing (0.0954 vs 0.0826 u at v110). But the two
    runs were up to 0.40 u apart there, on uneven ground.
  - Clean retest (`move-slope-001`): state `pokitaru-slope` saved at A0's
    post-landing spot, `walk` at stick angles ±25.6°, no R and no jump. C1
    matches A0 to 0.001 u (0.0009 u at +25.6°).
  - The earlier gap came from comparing different spots (INFERRED).
- **Small heading offset while walking, OBSERVED.** At the same stick angle
  (0°), the steady walking heading is −127.59° in A0 and −127.70° in C1
  (0.10°). Speed is the same. The `camera` fix does not change it.
  - This is why the position difference over a 2 s walk is 0.008 u, not the
    0.0005 u reported on 2026-10-19. That earlier figure compared path
    lengths; see the correction below.
- **Damage: blocked.**
  - Standing still for 15 emulated seconds in the bench state gave no hit.
  - No crab was located: the three groups tried were the vendor and two
    entities in the sea.
  - An execute breakpoint on the crab attack (module+`0x1254CC`, 2026-09-30
    log) did not fire within 8 s of the bench state: no crab attacks there.
- **Elevator: blocked.** The group guessed from code layout (callback
  `0x155CE4`, next to the Lvl3Elevator initializer `0x1563E8`) is not a solid
  platform: the player falls through at its position.

## Correction to 2026-10-19 MOVEMENT-REPORT.md

"Max deviation 0.0005 u walking" compared path lengths at equal emulated
times. Comparing 3D positions at equal emulated times (C1 at v−1 against A0 at
v) gives 0.008 u for the same run (`move-walk-001`) and 0.046 u for the running
jump (`move-walkjump-001`, angle 180°). The speed result (6.000 u/s in both) is
unchanged.

The difference comes from the 0.10° heading offset above, not from speed.
`tools/bench/move_compare.py` now does the position comparison.

## Runs (raw JSON outside Git, `D:/racsm60fps/work/runs/`)

| Run | Script / configs | Max position diff vs A0 (C shifted 1 vblank) |
| --- | --- | --- |
| `move-djump-001` | doublejump, gaps 8/16/24/32, A0 C1 | 0.0000 u for every gap |
| `move-longjump-001` | longjump (stick, R 56-68, cross 60), A0 C1 | 2.9928 u |
| `move-longjump-002-camera` | longjump, A0 C1 C1+camera (repeat of 001 for A0, C1) | C1 2.9928 u; C1+camera 0.3972 u |
| `move-walkr-001` | walkr (longjump without cross), A0 C1 | 0.0587 u |
| `move-slope-001` | walk at ±25.6° from `pokitaru-slope`, A0 C1 | 0.0010 / 0.0009 u |
| `damage-000-a0-probe` | damage_probe, A0, 15 s idle | no hit |

The A0 and C1 results of `move-longjump-002-camera` repeat `move-longjump-001`
to four decimals, so the bench is deterministic for these scripts.

Key double-jump values (A0 / C1):

| Gap (vblanks) | Apex above start | Airborne → landed (v) |
| --- | --- | --- |
| 8 | 1.688 / 1.688 u | 4→52 / 3→50 |
| 16 | 1.848 / 1.848 u | 4→60 / 3→59 |
| 24 | 1.240 / 1.240 u | 4→66 / 3→64 |
| 32 | 1.118 / 1.120 u (single jump) | 4→32 / 3→30 |

A0 samples at even vblanks only, so its lift and landing indices round up by
up to one vblank. The trajectory comparison above is the exact test.

`walkr` alone: Ratchet stops when R is pressed while running and stays still
after R is released, although the stick is still held. A window capture at the
end (A0) shows him at the water's edge: R turned the camera, so the
camera-relative stick now points at the sea and the shore stops him. The stop
point differs by 0.059 u (C1 slides further).

`longjump` is a script name, not the game's long jump: R here is the camera
yaw, and the apex equals a single jump (1.118 u).

## Tools added or changed (`tools/bench/`)

- `move_probe.py`: new `doublejump` (`--gaps`), `longjump` and `walkr` scripts;
  scripts are built per gap; results carry `gap`; `airtimeS` metric.
- `move_compare.py` (new): position difference and heading/distance views
  against A0 with the one-vblank shift.
- `damage_probe.py` (new): health (`+0x964`) and post-hit suppression
  (`+0x97C`) writes by breakpoint: hit times, HP lost, suppression duration.
  Untested on a real hit (no damage source yet).
- `entities.py` (new): pump-1 entity positions, nearest first; `teleport` test
  aid (writes player `+0x30..+0x38`). Records which callback groups are *not*
  crabs or elevators.
- `wordfix.py`: `apply()` now expands `camera` and the `ALIASES` of `fixes.py`
  and refuses unknown names. Before this, `apply()` silently skipped any name
  not in `DATA`: `C1+camera` would have run as plain C1. The CLI already
  refused unknown names. Earlier runs used only `DATA` names (`weapondt`), so
  they are not affected.

## Open questions for the owner

1. A savestate (or coordinates) next to a crab that attacks, and the crab
   group callback RVA. The public repo lacks the class atlas
   (`research/v2/c1-residual-timing-atlas/`), so classes print as `?`.
2. The Pokitaru elevator: its group callback, how it is triggered (step on,
   button, switch) and **when Lvl3Elevator initializes** (level load, approach,
   respawn). The `elevator` fix only acts at initialization
   (`docs/FIX_CATALOGUE_2026-10-01.md`), so a savestate taken after init would
   make `C1+elevator` measure plain C1. A state taken before init is needed.
3. Is the 0.10° steady heading offset while walking already known (stick
   filtering or turn smoothing with a per-call factor)?
