---
kind: static+live
title: "Crab and Pokitaru elevator located (Ghidra LEVEL_01) and measured on the bench: A0 / C1 / fixes"
date: 2026-10-22
authors: ["Claude (Opus 5.5)"]
related: [tools/bench/README.md, research/live-tests/pokitaru/session-2026-10-20-bench/REPORT.md, research/v2/crab-timer-audit-20261001/REPORT.md, patches/experimental/lvl3-elevator-halfstep/REPORT.md, docs/FIX_CATALOGUE_2026-10-01.md]
summary: "Both blockers of 2026-10-20 are lifted. Crab = group callback 0x126F28, Lvl3Elevator = 0x156710 (both already in level01-class-updates.json). Crab: C1+crab+crabtimers lands every hit 0.9008 s after the attack onset with a 3.370 s hit interval (A0 0.9009 s / 3.337 s; C1 3.003 s). Elevator: A0 10.01 s, C1 5.005 s; the `elevator` fix acts only at level creation; applied before the initializer from a cold boot, C1+elevator rides in 10.01 s (step 1/600)."
---

# Crab and Pokitaru elevator: located and measured (2026-10-22)

## Summary

- **Located (OBSERVED live).** The class table already in the repository
  (`research/v2/decomp-summary/level01-class-updates.json`) gives Crab =
  update `0x126F28` and Lvl3Elevator = update `0x156710`; these are the pump-1
  group callbacks. In `pokitaru-blaster` the Crab group has 58 slots and the
  elevator group one instance at (-127.0, -1.9, -49.0). The 2026-10-20 session
  had dismissed `0x126F28` as "entities in the sea": they are crabs, idle
  until the player enters their territory.
- **Crab measured (OBSERVED, 2 runs).** With Ratchet on the knoll at
  (33, 2.6, 21) (state `ghidra-crab`), crabs 7 and 8 chase and attack.
  `C1+crab+crabtimers` restores the attack wind-up (0.9007-0.9009 s vs A0
  0.9008-0.9009 s) and the cooldown state (0.5005 s vs 0.5005 s); hit interval
  3.370 s vs A0 3.337 s (+1.0 %). `crab` alone fixes only the first wind-up;
  plain C1 hits every 3.003 s, limited by the player's 180-substep invulnerability.
- **Elevator measured (OBSERVED).** Ride time from the live step and update
  interval: A0 10.01 s, C1 5.005 s (the published 10.01 / 5.00 s). The step is
  computed once by the initializer `0x1562DC` when the level's mobys are
  created, so applying `elevator` to a Pokitaru savestate measures plain C1
  (5.005 s, OBSERVED). From a cold boot,
  stopping on the initializer and applying `C1+elevator` there makes it
  compute 1/600 (it read 0 before: init not yet run) and the ride takes
  10.01 s at 59.94 updates/s (2 runs, OBSERVED). Saved as `ghidra-elev-c1fix`.
- **Riding to the top ends the level.** At progress 0.74 a story cutscene
  freezes the game and the level module is replaced (`rcp1` 0x46B900 ->
  0x484B00), and the game writes a save. A full ride is not timeable end to
  end; the probe measures the per-update step and the update rate instead.

## 1. Elevator (Lvl3Elevator)

### Static (Ghidra 12.1.3 + Allegrex, LEVEL_01 sha256 `d10a81d0...6571`, addresses = RVA)

| Address | Role | Evidence |
|---|---|---|
| `0x156710` | update (pump-1 callback); state machine on moby `+0x45` | decompiled; class table |
| `0x1562DC` | initializer "Lvl3Elevator_Init" (debug string); no direct caller, reached through the class descriptor | decompiled; no `jal` to it in 4848 functions |
| `0x1563E8` | `lui a2,0x3D08` building 1/30 in `step = (1/moveTime)*(1/30)` (the `elevator` fix word) | decompiled `piVar6[3] = (1/piVar6[1]) * 0.033333335` |
| `0x155E00` | "player on this elevator" test: module+`0x337C68` == moby (player's ground moby), height and radius checks | decompiled |

Data (pvar = moby `+0x54`): `+0x04` moveTime, `+0x08` progress, `+0x0C`
step, `+0x10` wait time, `+0x14` radius, bytes `+0x20..+0x26` options. Moby
`+0x45` state: 0 idle, 1 moving, 2 arrived (return trip), 3 waiting; `+0x70`
wait timer (adds the frame delta: correct in C1). In state 1 each update adds
step to progress and moves the platform along a smoothstep between two path
points; above 1.0 it goes to state 2 or 3.

Live values at Pokitaru (OBSERVED, state `pokitaru-blaster`): moveTime 10.0,
step 0.0033333 (1/300), progress 0, state 0, options `00 01 00 00 01 01 00`
(`+0x22` = 1: starts when the player stands on it).

**When does it initialize?** The step is already 1/300 in every Pokitaru
savestate examined, the initializer has no caller other than the descriptor,
and it sets the position from the path's first point: it runs when the level
creates its mobys (INFERRED from code + OBSERVED value; a respawn or
checkpoint reload was not tested). "Before init" therefore means "before
LEVEL_01 finishes loading". `elevator_probe.py preinit` gets there from a cold
boot with an execute breakpoint on `0x1562DC` and applies the configuration
at the hit, before the step is computed. Menu path on a fresh memstick
(2026-10-22): language (cross), the system "no data" dialog and "Save
completed" (circle: PPSSPP's dialogs confirm with circle here), main menu
"New Game" (down, cross), new save slot (cross); intro skipped with cross.
`preinit` presses `--buttons` in turn but cannot read the screen, so the
menus were driven by hand with window captures; from "New Game" on,
`--buttons cross,start` reached the hit.

### Measurements

| Config | State (where the step was computed) | Step | Updates/s | Ride (s) |
|---|---|---|---:|---:|
| A0 | `pokitaru-blaster` (A0 init) | 1/300 | 29.97 | 10.010 |
| C1 | `pokitaru-blaster` | 1/300 | 59.94 | 5.005 |
| C1+elevator, fix applied after init | `pokitaru-blaster` | 1/300 | 59.94 | 5.005 |
| C1+elevator, fix applied at the init breakpoint | `ghidra-elev-c1fix` (cold boot) | 1/600 | 59.94 | 10.010, 10.010 |
| A0+elevator (control, wrong pairing) | `ghidra-elev-c1fix` | 1/600 | 29.97 | 20.020 |

Runs `work/runs/ghidra-elev-002`, `-003`; preinit log
`work/runs/ghidra-elev-preinit-c1fix.json`: at the hit (pc = base +
`0x1562DC`, a0 = moby `0x096FD5F0`) the step was 0.0 and the word at
`0x1563E8` `0x3C063D08`; after `wordfix` C1+elevator the word was
`0x3C063C88` and, 2 s later, step 0.0016667 (1/600). The ride time from the
step and from progress per emulated second agree to 0.0001 s in every run.
The C1 init would also give 1/300: the C1 core words (`0x96650` and the
delta words) are not on the initializer's path (DEDUCED; not booted
separately). The A0+elevator row confirms the fix is C1-only (the
`lvl3-elevator-halfstep` warning).

Method: `tools/bench/elevator_probe.py ride` loads the state, applies the
configuration (`wordfix.py`), teleports Ratchet 1.4 u above the platform
origin (test aid), and records every write to progress (`+0x08`) and state
(`+0x45`) for 3 emulated s. Ride time = (1/step) updates x median update
interval; cross-checked with 1 / (progress per emulated second).

## 2. Crab

### Static

| Address | Role |
|---|---|
| `0x126F28` | update: decrements cooldown data`+0x64` every call, then dispatches on moby `+0x45` |
| `0x126750` | selector: `0x1266C8` (player inside the crab's territory volume pvar`+0x10`, not in pvar`+0x48`) then range test `0x29D94`; returns 0xD (attack) if cooldown < 1, 0xE (wait/decide) otherwise, 0xB (chase) out of range, 4 / 0x16 if the player is outside the territory |
| `0x1254CC` | state 0xD (attack): data`+0x60` += 1 per call; when >= float at `0x2CF3C8` (27.0) and hitbox `0xEE9C` overlaps, damage via `0x14A74`; leaves 0xD when the animation ends (`0x6AA08(moby,0)`) |
| `0x12744C` | state transition (reloads +0x60 / +0x64) |
| `0x127F18` | CrabObjectController update (2 instances) |

Data: moby `+0x54` = class data (territory volume `+0x10`, scale `+0x44`),
moby `+0x58` = per-instance pvar (`+0x60` attack counter, `+0x64` cooldown).
Why the 2026-10-20 breakpoint on `0x1254CC` stayed silent: no crab had the
player in its territory (all in states 1 / 4).

### Locating a crab for the bench

`entities.py teleport` wrote only `+0x30`; the game rebuilt y from other
copies and Ratchet fell through the ground, then respawned (OBSERVED twice).
Copies found by value scan of the player struct: `+0x70`, `+0x26C`, `+0x338`,
`+0xA88` (x, y, z) and `+0x2D0`, `+0x2D4` (y). Writing all of them holds
(OBSERVED: y stays 2.085 on the knoll). State `ghidra-crab` =
`pokitaru-blaster` + teleport to (33, 2.6, 21); crabs 6-8 (slots of group
`0x126F28`) engage within a second.

### Measurements (`damage_probe.py --state ghidra-crab --crab-slots 6 7 8 --seconds 12`)

Runs `work/runs/ghidra-damage-002` and `-003` (raw JSON, not committed).
Wind-up = hit time minus crab 8's latest entry into state 0xD (crab 7 also
attacks but its claw never reaches Ratchet: its gap is a constant 0.467 s).

| Config | Wind-up per hit (s) | Hit interval (s) |
|---|---|---|
| A0 (run 2) | 0.9007, 0.9008, 0.9009, 0.9009 | 3.3366, 3.3367, 3.3366 |
| A0 (run 3) | 0.9008, 0.9009, 0.9009, 0.9009 | 3.3366, 3.3367, 3.3366 |
| C1 | 0.8007, then 0.93-1.20 (hits gated by invulnerability) | 3.003 x3 |
| C1+crab (runs 2 and 3, identical) | 0.9008, then 1.03-1.25 | 3.003, 3.003, 3.0364 |
| C1+crab+crabtimers | 0.9007, 0.9009, 0.9008, 0.9009 | 3.370, 3.370, 3.3701 |

State durations (same runs): attack 0xD A0 1.168 s, C1 1.1845 s (animation
driven, +1 C1 frame); decide/cooldown 0xE A0 0.5005 s, C1 and C1+crab
0.2502 s, C1+crab+crabtimers 0.5005 s; player invulnerability (180 substeps)
A0 2.9701 s, C1 2.9867 s. HP lost per hit 1.0 everywhere.

Reading: the C1 defects are the cooldown (2x short) and the wind-up; `crab`
fixes the wind-up only, so later hits come as soon as the invulnerability
ends (3.003 s cadence instead of 3.337 s). With `crabtimers` the cadence is
within 1 % of A0 (residual: the attack state lasts one C1 frame longer).
Chase speed (`nav`, an InterpGate stub) is not word-level and was not tested.
A0 runs are not bit-identical from the same state (hit times shift by
0.05 s between runs 2 and 3); C1 runs are.

## 3. 30 Hz constants

See [CONSTANT-MAP.md](CONSTANT-MAP.md) (generated by `constant_map.py`, no
rescan: it consolidates the existing k30 audit, frames30, phase steps, frame
timers and clock maps). 26 of the 108 `1/30` literals have no fix
(PER_CALL_CANDIDATE). One of them was checked here: `0x6AA38` in `0x6AA08`
is an "animation ends within one 30 Hz frame" look-ahead (`len < t +
rate/30`), used only with a non-zero second argument; in C1 it fires at most
one 60 Hz frame early, not 2x (INFERRED; the crab path calls it with 0).

## 4. Bench changes (this branch)

- `elevator_probe.py` (new): `ride` and `preinit`.
- `damage_probe.py`: `--crab-slots` records crab states and wind-up; docstring
  pointed at the vendor group `0x1234D0` (wrong) and now at Crab `0x126F28`.
- `entities.py`: teleport writes every position copy; `list` skips inactive
  slots and shows the state byte; class map from `level01-class-updates.json`.
- `wordfix.py`: `apply()` no longer sends a pause to a CPU already stopped
  (at a breakpoint the stepping ack never comes and the call timed out).
- `damage_probe.py`, `abc_fire.py`, `move_probe.py`: `--instance`. Before,
  `--port 60908` drove instance 2 but `states.load` loaded the state into the
  default instance `ppsspp-1` (another session's).

## 5. Evidence levels

- OBSERVED: group callbacks and live fields above; all timings in sections 1-2;
  cutscene + module switch at progress 0.74; position copies.
- DEDUCED from decompiled code: state meanings, trigger test, step formula,
  initializer reached only through the descriptor.
- INFERRED: initializer runs at level creation only (not re-run on respawn;
  untested); `0x6AA08` look-ahead impact.
- UNKNOWN: which crab-state reload sites matter outside this fight; the
  return trip of the elevator (blocked by the end-of-level cutscene).

## 6. Questions for the owner (relayed by Antoine)

1. Is the Pokitaru elevator the end-of-level lift (cutscene at the top, then
   the next module 0x484B00)? Your 10.01 / 5.00 s: measured on a full ride
   after the cutscene was seen, or from the step?
2. Does Lvl3Elevator re-initialize on death or checkpoint reload? A cheaper
   "before init" path than a cold boot would help the bench.
3. In C1 the first crab hit lands 0.80 s after the attack onset, not 0.45 s
   (27 calls at 60 Hz): does the hitbox `0xEE9C` follow the claw animation?
4. `crabtimers` + `crab` match A0 within 1 % here; any crab state you still
   see as wrong (chase, retreat, burrow)?
