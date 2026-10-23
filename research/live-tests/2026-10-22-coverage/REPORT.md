---
kind: live
title: "Bench coverage beyond Pokitaru: Ryllus (LEVEL_02) reached and measured, cadence of every weapon, per-level port of the bench"
date: 2026-10-22
authors: ["Claude (Opus 5.5)"]
status: partial
evidence: [OBSERVED, INFERRED, UNKNOWN]
systems: [player, movement, camera, weapons, tooling, level-loading]
levels: [Pokitaru, Ryllus, Kalidon Skyboard]
variants: [A0, C1, C1+weapondt, C1+camera]
environment: "PPSSPP 1.20.4 portable (instance ppsspp-1, port 60907), Direct3D 11, JIT, plugins off, no InterpGate; CPU 222 MHz; window in background; two other PPSSPP instances running on the same host"
supersedes: []
related: [tools/bench/README.md, research/live-tests/pokitaru/session-2026-10-20-bench/REPORT.md, research/live-tests/pokitaru/session-2026-10-19-bench/REPORT.md, tools/runtime/fixes.py, cheats/eu/base/]
summary: "The bench now reaches and ports any level. On Ryllus (LEVEL_02) clock, Blaster, Bomb Glove and BlitzGun are halved in C1 and weapondt restores them; walk, jump and double jump match A0. LaserTracer drain x2 and Ryno +7 % reproduce (known, plugin-only fixes). New: a ~7 deg heading overshoot when starting a sideways walk, on Pokitaru too, not changed by the camera fix. Gadgets, damage, projectiles and timed effects untested."
state: "banc-ryllus-* (LEVEL_02 from a new game, reached with level_route.py), banc-skyboard-arrive (LEVEL_22), pokitaru-blaster"
---

# Bench coverage, 2026-10-22: Ryllus and every weapon

Five-line summary:

- The bench now runs on any level module: `level_route.py` reaches a level
  from boot, `level_port.py` ports every LEVEL_01 constant and fix site
  offline, and the C1 core it finds equals the owner's cheats wherever a
  cheat exists.
- Ryllus (LEVEL_02) behaves like Pokitaru. Clock, Blaster, Bomb Glove and
  BlitzGun are halved in C1, and `weapondt` restores them. Walk, jump and
  double jump match A0.
- LaserTracer ammo drain x2 and Ryno refire +7 % reproduce on Ryllus. Both
  were already known, and their fixes are plugin code (FG-v4, `animlat`)
  that the word-level bench cannot apply.
- New: a heading overshoot of about 7 degrees when starting a sideways walk
  (Pokitaru too). The `camera` fix does not change it.
- LEVEL_22 (skyboard) is reached, and its ported C1 core runs at 1 vblank
  per frame. The board itself was not measured.
- Not tested: gadgets, board and vehicle handling, projectile speed and
  lifetime, timed effects (shield), damage. Every other level is checked
  offline only.
- Pokitaru did not regress with the new code: fire 1.998 / 0.983 / 1.998
  shots/s, walk maxDiff 0.008 u.

## Method

Same bench as 2026-10-19/20 (`tools/bench/README.md`): emulated time,
frame-locked input, write breakpoints, one savestate per test so every
configuration starts from the same emulated state. Configurations:

- `A0`: original game.
- `C1`: the owner's 60 FPS core (vblank limiter bypass, main delta 1/60,
  substep loop 2 -> 1), from `tools/runtime/pump-gate.py`.
- `C1+<fix>`: C1 plus word fixes of `tools/runtime/fixes.py` (`DATA`).

New this session:

- **Level access.** BOOT.BIN keeps a table of 40-byte module paths
  (`disc0:/PSP_GAME/USRDIR/BIN/LEVEL_NN.PRX`, file offset 0x3A05C for
  LEVEL_01). Rewriting the two digits of the LEVEL_01 entry in RAM at the
  frontend, then starting a new game, loads another level. The module loads
  its own art WAD, and the save is the new-game one (wrench, Blaster, Bomb
  Glove). Ryllus loads at base 0x09139D00, the Pokitaru base, with
  `rcp1` size 0x484B00.
- **Port.** `level_port.py` matches LEVEL_01 code and data against each
  level PRX. The match masks relocated fields (jump targets, `lui`
  immediates, load/store offsets, non-`sp` `addiu`/`ori`) and widens the
  window until the match is unique. Data addresses are voted on from
  `lui`/offset pairs. HI16/LO16 relocations are relative to the segment
  they point into (README pitfall 14).
- **Weapon test aid.** Writing `player+0x99C` (requested weapon id) equips
  any weapon with its model and HUD. The game copies it to `+0x998` at
  LEVEL_02 code RVA 0x1F2EC. Tools: `fire_rate.request_weapon`,
  `abc_fire.py --weapon N`.

Host: three PPSSPP instances on the same machine, CPU 33.1 % average over
10 s before the fire runs. Emulated-time results do not depend on it.

## Coverage table

Cell legend:

- **M**: measured live, run id given.
- **P**: ported offline only (core, data addresses and fix sites matched),
  nothing run.
- **p**: partly ported (vblank site only; delta, substep loop and weapon
  table not matched).
- **-**: not tested.

Levels 03-10, 15, 21-24 are all P, and 16-20 are all p, for every row.
The ISO has no LEVEL_11 to LEVEL_14.

| Mechanism | Pokitaru (01) | Ryllus (02) |
| --- | --- | --- |
| Game clock (ticks per frame) | M (10-19) | M `clock` 8 s: A0 2.00 vblank, C1 1.000 |
| Blaster V1 / V4 cadence | M (10-19), regress M | M `banc-ryllus-fire-001/-002` |
| Bomb Glove | - | M `banc-ryllus-bomb-001` (3 shots, low sample) |
| Other weapons (ids 3, 5, 6, 8-11, 15) | BlitzGun, Ryno: parity doc 10-02 | M `banc-ryllus-w<id>-001` |
| SuckCannon, Mootator | - | - (stock 0 in the state) |
| ShieldCharger, MiniTurret | - | - (equip refused, see below) |
| Walk 0 deg | M (10-19), regress M | M `banc-ryllus-walk-001` |
| Walk 45 / +-90 deg | M `banc-pokitaru-walk-004-pm90` | M `banc-ryllus-walk-002/-003` |
| Jump, double jump | M (10-20) | M `banc-ryllus-jump-001`, `-djump-001` |
| R + jump (camera yaw) | M (10-20) | - |
| Damage / health | blocked (10-20) | - |
| Projectile speed and life | - | - |
| Timed effects (shield, buffs) | - | - |
| Gadgets | - | - |
| Vehicles / skyboard | n/a | n/a; LEVEL_22 clock M `banc-level22-clock`, board M 2026-10-23 (`../2026-10-23-skyboard/REPORT.md`) |
| Crab, elevator | sister session `ratchet-ghidra` | `elevator` site ported 0x16B050, not run |

Port per level (`work/runs/banc-port/summary.json`):

| Level | Core / addresses | Fixes ported, cheat check |
| --- | --- | --- |
| 02, 03, 04, 05, 06 | all | 178-203 of 327; core = cheat sites |
| 07, 08, 09, 10, 24 | all | 183-202; no owner cheat to compare |
| 15 / 21 | all | 67; 15 = cheat; same profile (pitfall 17) |
| 16, 17, 18, 19, 20 | vblank, frame counter, player, entities | 57-110; no `weapondt` |
| 22 | all | 95; core = cheat sites |
| 23 | all | 181; cheat site differs (question 1) |

`weapondt` and the camera filter fixes port to every level except 16-20.
`crab` ports nowhere. `elevator` ports to 02, 03, 07 and 24.

## Results, Ryllus (LEVEL_02)

All OBSERVED. Each run was repeated twice with identical results, unless
noted. Fire runs held the button for 4 s (Blaster: 6 s).

| Weapon | A0 / C1 / C1+weapondt (shots/s) | Verdict |
| --- | --- | --- |
| Blaster V1 (2) | 1.998 / 0.983 / 1.998 | halved, fixed |
| Blaster V4 (`--rank 3`) | 3.746 / 1.998 / 3.746 | halved, fixed |
| Bomb Glove (4) | 0.659 / 0.331 / 0.659 | halved, fixed |
| BlitzGun (3) | 1.303 / 0.659 / 1.303 | halved, fixed |
| AgentsGlove (5) | 0.333 / 0.333 / 0.333 | equal (2 shots only) |
| BeeMine (6) | 0.333 / 1 shot / 0.331 | C1 slow, fixed (+1 vblank) |
| ShockRocket (8) | 0.999 / 0.999 / 0.999 | equal |
| Crossbow (9) | 1.303 / 1.303 / 1.303 | equal |
| Flamethrower (10) | 3.996 / 3.996 / 3.996 | equal rate; median gap 0.267 / 0.250 s |
| LaserTracer (11) | 11.99 / 23.98 / 23.98 | drain x2, known; plugin fix only |
| Ryno (15) | 2.017 / 2.141 / 2.141 | C1 +7 %, known; plugin fix only |

Weapon notes:

- First shot after the press: Blaster A0 2.02 vblanks, C1 1.02. Bomb Glove
  A0 18.08, C1 31.08, C1+weapondt 17.07. LaserTracer A0 8.01, C1 4.01.
- LaserTracer, same point, `banc-ryllus-w11-002-laserfix`. These fixes were
  applied (5 and 8 word writes) and the drain stayed 23.98/s:
  - `C1+laser1+laser2`;
  - `C1+laser1+laser2+laserfadein+laserfadeout+weapondt`.
  `laseracc` is in the `RUNTIME` family of fixes.py, which wordfix cannot
  apply. The defect was already known: `docs/WEAPONS_60FPS_STATUS_2026-10-03.md`
  found it on Quadrona, with doubled damage too. The cause is an ammo
  countdown gated by a "first substep" flag that is always set at 60 FPS.
  The fix is a code patch (FG-v4) and was not run here.
- Ryno: the median gap is 0.5005 s in A0 and 0.467 s in C1, 15 against 28
  60 Hz frames. This matches `docs/WEAPONS_PARITY_2026-10-02.md` on
  Pokitaru, where the cause is animation end latency. That doc's fix is
  `animlat`, an InterpGate wrapper (IG-v20) that gave 30.08 frames, and it
  is not runnable with wordfix. `rynorate` is rejected
  (`tools/runtime/fixes.py`, line 340).
- ShieldCharger (7): requesting it uses one charge (5 -> 4) and the game
  falls back to the Blaster. MiniTurret (14) falls back the same way. Both
  need their own activation path.

Movement:

- **Walk 0 deg** (`banc-ryllus-walk-001`): maxDiff 0.0258 u (Pokitaru
  0.008). Steady heading 170.08 deg in A0, 169.93 deg in C1. Speed 6 u/s
  in both.
- **Walk 45 deg** (`-002-angles`): maxDiff 0.0039 u, against an obstacle.
- **Sideways walk +-90 deg** (`-003-camera`, A0 / C1 / C1+camera). C1 turns
  further than A0 during the first second, then the heading gap stays
  constant. The comparison shifts C1 by one vblank.

  | Vblank | Heading gap, -90 deg |
  | --- | --- |
  | 12 | 0.67 deg |
  | 32 | 3.1 deg |
  | 52 | 5.8 deg |
  | 72 | 7.0 deg |
  | 102 | 7.46 deg |

  - At +90 deg the gap reaches a plateau near 7.5 deg.
  - After the plateau, both turn at about 1.1 deg per vblank.
  - C1 is bit-identical across repeats.
  - `C1+camera` equals `C1` exactly: 13 words written, no effect.
  - Pokitaru, same test (`banc-pokitaru-walk-004-pm90`): same shape
    (0.46 deg at vblank 12, 5.0 at 52, 6.5 at 72), and `camera` has no
    effect there either.
  - INFERRED: a smoothing step that converges per call (camera follow, or
    turning toward the stick direction) runs twice as often in C1. This is
    not the R-yaw case of 10-20, which the `camera` fix does restore.
- **Jump** (`banc-ryllus-jump-001`): maxDiff 0.0000 u, apex 1.118 / 1.120.
- **Double jump**, gaps 8/16/24/32 (`-djump-001`): 0.0000 u everywhere. The
  window closes between 24 and 32 vblanks, as on Pokitaru.

## Pokitaru non-regression (new code)

| Run | Result | Reference |
| --- | --- | --- |
| `banc-pokitaru-regress-001` fire, 6 s | 1.998 / 0.983 / 1.998 | 10-19: same |
| `banc-pokitaru-regress-002-walk` | maxDiff 0.008 u | 10-19: 0.008 |
| `banc-ryllus-weaponflag-001` (`--weapon 2` from the BlitzGun state) | Blaster equipped, 1.998 / 0.983 | `-fire-001` |

## Owner cheat anomalies (bytes OBSERVED, effect INFERRED)

- LEVEL_03 substep loop: the cheat writes 0x2A200001, `slti zero,s1,1`.
  The result goes to `zero` and is lost; every other level writes
  0x2A240001 (`slti a0,s1,1`). If the effect is what it looks like, the
  loop keeps its original condition.
- LEVEL_23: the loop cheat targets 0x294D8, which holds `bne a0,zero`
  (0x1480FFEB). The `slti` is at 0x294D4.
- LEVEL_06: the cheat has a second delta site, 0x144500 (`lui a0,0x3D08`),
  which the bench's C1 core does not include. C1 on LEVEL_06 is therefore
  not the owner's patch.

## LEVEL_22 (Kalidon skyboard): reached, clock only

The first attempt redirected only the LEVEL_01 entry. The title screen
resumed the save that the game had written on arrival at Ryllus (memstick
`SAVEDATA/UCES00420DATA0`), so it loaded LEVEL_02 again. `level_route.py`
now redirects every LEVEL entry and restores them from BOOT.BIN. The second
attempt was resident after 12 presses: `rcp1` 0x3CF100, base 0x09139D00,
ship arrival scene. State: `banc-skyboard-arrive`.

Clock, 6 s from that state (`<root>/work/runs/banc-level22-clock.log`):

- A0: 8.18 M ticks per frame, 2.21 vblanks. The arrival scene drops some
  frames to 3 vblanks.
- C1: 3.70 M ticks per frame, 1.000 vblank.
- The ported core wrote RVAs 0x1239C (delta), 0x26794 (loop) and 0x87F18
  (vblank). These are exactly the owner's LEVEL_22 cheat addresses minus
  the base.

Board speed, steering, jumps and race timers were not measured here. They
were measured on 2026-10-23 from this state:
[2026-10-23-skyboard/REPORT.md](../2026-10-23-skyboard/REPORT.md).

## Questions for Linkinito

Kept apart: they are relayed by Antoine, never sent from here.

1. LEVEL_03 (`slti zero,s1,1`) and LEVEL_23 (cheat on the `bne` word, not
   the `slti`): are these intended?
2. LEVEL_06, second delta site 0x144500: what does it drive?
3. Sideways walk: C1 turns about 7 degrees further during the first second
   on Pokitaru and Ryllus, and the `camera` fix has no effect. Known? Which
   routine smooths the heading?
4. Does his patch handle the LaserTracer (ammo drain and damage x2 in C1)
   and the Ryno refire (animation end latency, +7 % in C1)? The repo fixes
   are plugin code (FG-v4, `animlat`).
5. ShieldCharger and MiniTurret: how are they activated? The bench cannot
   equip them by id.
6. LEVEL_16-20: delta, substep loop and weapon table do not port. How is C1
   done there?

## Files

- Tools (commit 1dc43c4; `level_route.py` all-entry redirect in the commit
  that adds this report): `tools/bench/level_port.py`, `levels.py`,
  `level_route.py`, plus edits to `wordfix.py`, `breakloop.py`,
  `clock.py`, `fire_rate.py`, `abc_fire.py`, `move_probe.py`,
  `damage_probe.py`, `entities.py`, `README.md` (pitfalls 14-17).
- Raw results (not committed):
  - `<root>/work/runs/banc-*`, port tables in `<root>/work/runs/banc-port/`;
  - weapon batch log `<root>/work/runs/banc-ryllus-allweapons.log`;
  - states `<root>/work/states/banc-ryllus-{start,blaster,bomb,w3..w15}.ppst`.
