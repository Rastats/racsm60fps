# Fix catalogue — ready for live testing (2026-10-01)

**Audit correction:** the generated Crab timer batch is REJECTED and activation
is quarantined: ten of its 29 unique sites change animation identity, object
flags or wave capacity. Status/restoration remain available. The earlier owner
observation is retained, not generalized to acceptance of the batch. See
[the audit](../research/v2/crab-timer-audit-20261001/REPORT.md). Other classes
from the same generator require explicit dataflow review before live use.

**Context correction (2026-10-02):** the call-context map
([report](../research/v2/call-context-20261002/REPORT.md)) shows that 10 `frametimers` sites and the
phase constant `0x2B0E70` sit in player substep code that already runs 60 calls/s in A0 and C1; they are
removed from the groups (individual keys kept). New static candidates: `framescale` (player frame scale
+0x578, `0x360E8` x30 -> x60), `skyrot` (sky angle step `0x2D47D8` halved), alias `domain8` =
`weapondt` + `substepdt` + `framescale`. `rynorate` needs the Ryno probe first (may be already correct). Also new from the 1/30 re-audit:
`teleporterfx` (Teleporter effects, 7 sites), `groupfade` (4 global fade channels, role UNKNOWN),
`k30calls` (pickup pop motion, flying cars, TieManipulator, crank cam, Polarizer, beacon; 11 sites).
TrainingBot generated list quarantined (anim id + half window); reviewed `tbtimers` (12 words).
**Weapons session (2026-10-02 evening, measured):** see [WEAPONS_PARITY_2026-10-02.md](WEAPONS_PARITY_2026-10-02.md).
TESTED 1:1 (single location): `weapondt` (Blaster 4.133 vs 4.134 shots/s; Tremblator 46.0 vs 23.0x2
frames), `blastershot` (speed 125.7 vs 125.9 u/s), `rynorocket` (23.94 vs 23.97 u/s), `animlat`
(IG-v20; Ryno 30.08 vs 15.0x2 frames). REJECTED by measurement: `rynorate`. New plugin builds:
IG-v20 animlat, IG-v21/22 rayhalf, IG-v23 particle mode 3 (`segrate`), IG-v24 30 Hz islands
(`blitzhalf`, `raycb`, untested). Data aliases `blitzshot`, `rayfix`, `segfade` (Tremblator rays, not 1:1).
The fix tool rewrites the preceding branch after a delay-slot edit (PPSSPP JIT); earlier tests of
delay-slot sites (weapondt, substepdt, 3 crabtimers words, frames30 0x14F218, frametimers 0x16D014,
lunaidle1, k30calls 0x17A6D0, tbtimers 0x18531C) may not have been active.
**Weapon-context check (static, 2026-10-02 end):** the equipped weapon's update runs in the player substep
loop (already 60 calls/s in A0 and C1). Fix sites only reached from weapon updates: `laser2`, `laserfadein`,
`laserfadeout` (LaserTracer weapon functions) are probably double corrections, measure before use;
`ft0x16d014` (ShieldCharger) and `f300x11a1e0` (BlitzGun) removed from their groups; Crossbow frames30
sites are mixed-context (weapon + projectile), removed from the group. Spawn-time values handed to
pump-1 projectiles (`bshot_speed`, `rr_speed`) stay valid (measured). Details:
research/v2/weapons-static-20261002/ (local research branch).
Suggested order: `domain8` (Blaster meter), `teleporterfx`, `k30calls` (crate pickups), `skyrot`.

All entries are experimental and derived statically from the full LEVEL_01
decompilation, except where "owner-accepted" is stated. None is a measured
parity result. Apply them with `tools/runtime/fixes.py` (InterpGate **IG-v16f**
installed as the only plugin; the tool refuses another loaded build) or
`tools/runtime/timer-patches.py`. Measure them with `tools/runtime/fix-monitor.py`
(see "Numeric monitoring" below).

| Fix | Mechanism (static) | Classes | Status |
|---|---|---|---|
| `nav` | displacement vector halved before `0x2A8F0` (now asm stub, registers preserved) | Crab, TMRobotHeadB/TorsoB, TrainingBot | crab speed owner-accepted (C wrapper 2026-09-30; asm stub IG-v16f 2026-10-01) |
| `nav2` | same for the second navigation move `0x2935C` (site `0x29164`) | same | untested |
| `cows` | same for `0x190D6C` / `0x191154` / `0x1913A4` (sites `0x190388`, `0x1915F4`, `0x19163C`) | MutantCow, MutantMadCow, AgentOfDoom | untested |
| `crab` | attack threshold data `0x2CF3C8` 27 -> 54 | Crab | owner-accepted |
| `timer-patches.py --class Crab` | generated 45 rows / 29 unique sites; 19 reload candidates, 10 non-timer sites; misses float-derived cooldown +0x64 | Crab | **REJECTED batch; activation blocked**. Historical attack-rhythm observation retained; replacement and parity measurements pending |
| `crabtimers` | reviewed replacement (`research/scripts/crab-timer-recipe.py` -> `crab-timer-audit-20261001/crab-timer-recipe-v2.json`): the 19 corroborated data+0x60 reload sites x2 (random `rand%m+o` -> `rand%2m+2o`, same range in seconds) and the data+0x64 cooldown `trunc(helper*15.0)` -> 30.0 at `0x12754C`; the ten rejected sites stay original | Crab | untested (needs a clean boot, A0 baseline, then `--fix nav,nav2,crab,crabtimers`) |
| `timer-patches.py --class TrainingBot` | state durations x2 (30/60, 60/90 frames, threshold 53) | TrainingBot | untested |
| `frametimers` | 29 hard-coded `1/30` timer steps -> `1/60` (EnemyWave state 1 `0x137F5C`, Help `0x150F0C`, Teleporter `0x64FA0`, ElectroshockWave, AgentsRocket, Polarizer, ShieldCharger, TMRobotHeadB, shots) | 9+ classes and engine paths | untested (subset of the rejected F1) |
| `laser` | LaserTracer adds 1.25 (`0x149828`, beam active) and 1.5 (`0x145568`) to field `+0x68` per call; both data constants (`0x2D2D68`, `0x2D2D80`, LaserTracer-only) halved | LaserTracer | untested; role of `+0x68` (drain accumulator) INFERRED |
| `frames30` | 17 `lui 0x41F0` (30.0) in seconds->frames conversions and per-frame rates -> 60.0 (boat countdown `0x14F218`, Crossbow x3, BlitzGun, HUD/pickup timers `0xA3xxx/0xA5xxx`, RatchetShipAnimation, crab/bee random timers `0x191CF0`, particle animator `0x60100` x3) | Level01Boat, CrossbowGun/Shot, BlitzGun, pickups, HUD, ship animation, particles | untested; Blaster site `0x117B70` deliberately excluded |
| `elevator` | Lvl3Elevator initializer `0x1563E8` computes `(1/moveTime)*(1/30)` -> `1/60` (legacy recipe) | Lvl3Elevator (Pokitaru elevator measured 10 s -> 5 s in C1) | untested in this form; takes effect when an elevator initializes |
| `boatfade` | Level01Boat per-call fade/progress step `0x2D42FC` (1/15) halved | Level01Boat | untested |
| `age70` | entity age `+0x70 += 1.0` per call -> 0.5 (11 sites; BeeMine/BlitzGunShot/RynoRocket added after register-liveness review, `level01-age70-reviewed-sites.json`) | BlasterShot, ShockRocketShot, FlyingCar x3, SwarmManager, SuckCannonComet, RynoRocket, BlitzGunShot, BeeMine (bee release every 8 age units) | untested |
| `particles` | generic animator half-step (IG-v13) enabled for the waterfall animator `0xDE23C` only | waterfall mist/splashes | untested |
| `particles-all` | REJECTED live 2026-10-02 (multicoloured mist/splashes: packed colour words halved; crate debris and waves still 2x). Was: same for all 47 registered animators (`level01-particle-pools.json`): changed plain floats keep half their change; slot identity learned from death-free calls; rotated unit vectors renormalised | all particle pools (crate debris `0x1A05F0`, fire, sparks, ...) | untested |
| `waterfall` | spawn parity `(n+1)&1` -> `&3` at `0x151EDC` (spawn every 4th update), texture scroll steps `0x2D4890`/`0x2D4894` halved | Level01Waterfall (spawn density, "vaguelettes") | 2026-10-02: quantity OK, mist/splash speed and water scroll still 2x (scroll source UNKNOWN) |
| `camera` (+ negative caps `0x3634`/`0x37F8`) | 1/30 -> 1/60 in camera input/yaw/pitch/follow; the -1/30 caps were missing at first (left turn stayed 2x) | camera | owner-accepted 2026-10-02 |
| `frames30` (HUD) | x30 conversions incl. HUD timers | HUD | HUD hide delay owner-accepted 2026-10-02 (2 s); bolts flying to Ratchet still 2x |
| `weapondt` | 2 x delta into P_Player_WeaponUpdate (delay slot `0x2FCF4`) | weapons | REJECTED as the Blaster fix: rate unchanged (cooldown is not the limiter). Blaster A0 4.2 shots/s vs C1 2.0 shots/s (measured) |
| `substepdt` | 2 x delta into `0x39B74` (delay slot `0x2FCE8`), role UNKNOWN | player/weapons | experiment prepared, untested |
| `physstep` | IG-v18 half-step on `0x2832C` (life -1, pos += vel + g/2, vel.y += g per call) for the bolt pool and the generic physics pool fed by crates | bolts flying to Ratchet, crate debris | untested (owner saw both 2x) |
| `particles-rate` | IG-v19: every particle animator still runs every frame (drawing) but its records are restored byte-exactly on every second update (30 Hz state, no field-type assumption) | all particles incl. waterfall mist/splashes, teleporter effect, waves | untested; replaces the rejected particles-all |
| `camfilters` | exact 60 Hz conversion of the 20 critically damped camera filters: init literal `0xCA2C` 1/30 -> 1/60, computed k = omega/30 -> omega/60, exp(-omega/30) -> sqrt | camera follow/placement smoothing; **cause of the sideways-walk heading overshoot** (stick read relative to the camera yaw) | measured 2026-11-08 (bench, `research/live-tests/2026-11-08-heading-fix/`): heading gap to A0 at 1 s, ±90 deg walk, 5.7-6.9 deg (C1) -> 0.48-0.91 deg, Pokitaru and Ryllus; camera feel not judged by the owner yet |
| `rynorate` | Ryno refire counter 24 -> 48 frames (`0x2D6A90`), if Ryno_Update runs once per frame (probe Ryno/refire70 first) | Ryno ("TELT") | candidate, untested |
| `helphint` | wrench-throw hint after 18000 frames: `sltiu` at `0x150FC0` -> 32767 (9.1 min at 60 Hz; 36000 does not fit) | Level01HelpManager | untested |
| `infammo` | ammo decrement neutralised (9 `addiu -1` + LaserTracer 2) | TEST AID | works for all owned weapons except Acidbomb; SuckCannon excluded (broke it) |
| `butterfly` | flap/speed steps halved (`0x2CEDA8..B4`), speed spring refit, + `timer-patches --class Butterfly`; values are drawn at butterfly init | Butterfly | owner-accepted 2026-10-01 (with a live instance edit for existing butterflies; telemetry x1.00 vs A0) |
| `firerate` | Fire_Update emission accumulator `acc += 0.667` per call -> 0.333 (`0x2D1708`, Fire-only) | Fire (particle density) | untested |
| `phases` | 24 exclusive per-call fade/countdown/phase constants halved (`level01-phase-steps.json`): HUD fades, ocean sound fade, BeeMine/ExplosiveBee/decoy/beacon countdowns (17.0 -> 8.5, int truncation gives 9: ~6% fast), ShockRocket/ShrinkBeam phases, SuckCannon | HUD, sound, gadgets, projectiles | untested |
| `clock` | 19 lui/lw pairs in 14 clock users of the frame counter `0x2AF28C` load a half-rate copy kept by the plugin (`level01-clock-sites.json`): `& 1/3`, `% 3/5/n` triggers, spark deadline, input double-press window, camera input stamp, **skill point "train faster" window 0xAC8** | Polarizer, AgentsGrenade, LaserTracer sparks, SkillPoint_L01, ... | untested; do not combine with a 2760->5520 skill-point patch (would be 4x) |
| `pathanimals` | walk speed x0.5 (IG-v13 stub at `0x15DE70`), turn spring refit, fall gravity /4 | PathAnimal | untested |
| `springs` | engine spring `0xE290` (`v = (t-x)k - v d; x += v` per update): 28 constant {k,d} structs refitted for 60 Hz on the step response (`level01-spring-params.json`; e.g. 0.1/0.2 -> 0.0633/0.4864) | turning of Crab, TM robots, Butterfly, boat, Luna, PathAnimal; HutDoor, TriggeredDoor, CrankedObject | untested |
| `luna` | LunaNPC step `0x2D4EA8` halved (jump arc is solved per frame from distance/step, so it stays consistent), idle timer `rand%30+15` x2, Luna springs | LunaNPC, LunaCutscene | untested |
| `spawn` | IG-v15 throttle on the pool allocator (`0x8C894`, `0x8C8E4`): a call site that spawned in the previous update keeps half its count, bursts unchanged | particle density of every continuous emitter (trails, smoke, sparks) | untested; with `waterfall`/`firerate` those emitters are no longer consecutive and are not throttled twice |
| `laserbeam` | beam fade-in 15 -> 30 and fade-out 6 -> 12 frames (`0x2D2DD4/D8`), 32 layer texture-scroll steps halved | LaserTracer beam | untested |
| `crank` | BoltCrankBolt frames step 1.0 -> 0.5 (`0x120C38`) and runtime drop step `0x2CE884` halved live | BoltCrankBolt | untested |
| `laseracc` | LaserTracer runtime accumulator step `0x2D2D74` halved live | LaserTracer | untested; role INFERRED |
| `debris` | shrapnel physics `0x191D7C` half-step | enemy shrapnel (not crates) | runs; visual effect unconfirmed |
| `animdisp` | `0x6C318` | - | **REJECTED (static)**: it writes `out = moby pos + offset` (`0x6C2B8` -> `0xF5624` copies the position), an absolute point, not a per-call step; the freezes came from register use |

## Category review (static, 2026-10-01)

Verdict table for every class: `research/v2/decomp-summary/LEVEL01-CLASS-VERDICTS.md`.

- **Held weapons** (Blaster, Flamethrower, AgentsGlove, LaserTracer gun logic) run in
  the player weapon update inside the player substep loop; C1 keeps their call rate
  (earlier measurements: AgentsGlove counters, Flamethrower phase unchanged). Blaster
  cooldown is delta-based. LaserTracer drain was measured 2x -> `laser`.
- **Projectiles** mostly move with the delta (ShockRocketShot, RynoRocket, Acidbomb);
  BlasterShot moves `pos += vel` per call and, like several others, ages `+0x70 += 1.0`
  per call (`age70`). Crossbow/BlitzGun use x30 frame conversions (`frames30`).
- **Enemies/NPCs**: ground navigation (`nav`, `nav2`), cows/Agent of Doom (`cows`),
  crab/training bot state timers (`timer-patches.py`); Sharkagator/fin, Mootator use the
  delta; PathAnimal moves `pos += forward * speed-per-call` (config `+0x54 -> +4`) — needs
  a per-instance speed halving or a stub (not built); Butterfly flap `0x122C98` known.
- **Vehicles/platforms**: DropshipB (enemy ship) movement uses the delta; Lvl3Elevator
  progress `+8 += +0xC` per call (wait timer uses delta) -> halve the increment (legacy
  initializer recipe in `patches/experimental/lvl3-elevator-halfstep`); Level01Boat
  countdown `seconds x 30` and fade step (`frames30`, `boatfade`); flying cars age
  (`age70`); BoltCrankBolt height `+0x34 += const` and `+0x70 -= 1.0` per call (not built);
  TriggeredDoor, ZipLine, Slide: no timing shapes found (animation-driven, likely fine).

Not a defect (static): Blaster cooldown and shot timer use the delta
(`Blaster_Update(dt, ...)`), so no correction is needed under C1.

Closed in the follow-up session: projectile ages (age70), LunaNPC (luna), particle density (spawn),
laser beam (laserbeam), springs, float clock users `0x104C80`/`0x8341C` (clock, 21 groups).
EnemyWave `+0x15C` is an enemy count, not a timer (no fix). Left on the game counter on purpose:
`0x54EFC` (stamp read outside LEVEL_01?), `0x77098`/`0x783B0` (cache last-use stamps), `0x106698`
(object spawn stamp, readers unknown). `pathturn` is superseded by the spring refit.
Remaining static work: reopen LEVEL_01 timer dataflow review after the Crab batch
rejection; other levels and FRONTEND/EBOOT remain pending. Do not port the rejected batch.
Rejected (static): pickups `0x7248` is a look-at matrix builder (ArmorPickup/TitaniumBolt camera),
not a displacement integrator.

## Numeric monitoring (IG-v12+)

`fixes.py ... --fix <fixes>,telemetry` redirects the pump-1 call to `ig_tel_pump`, which
samples up to 64 watches once per main update (read-only) and sums the delta passed to pump 1.
`fix-monitor.py --seconds 10 --out <dir>` then lists active entities, watches timing probes
(crab/training-bot state timers, elevator progress, boat fade, crank frames) and the position
of up to two instances per active class, and writes `report.md`: updates per game second,
hook call rates, top/active rates per game second, timer reload durations in seconds with
the static A0 expectation, and per-animator corrected particles. For parity numbers record an
A0 baseline at the same place first:

```text
python tools/runtime/fixes.py --target A0 --fix telemetry --out <dir1>
python tools/runtime/fix-monitor.py --seconds 15 --out <dir2> --save-baseline <base.json>
python tools/runtime/fixes.py --target C1 --fix <fixes>,telemetry --out <dir3>
python tools/runtime/fix-monitor.py --seconds 15 --out <dir4> --compare <base.json>
```

Ratios near 1.0 (OK) mean the measured rate in game seconds matches A0; ~2.0 means still
2x fast. These are telemetry values (TELEMETRY_NOT_GAMEPLAY_VALIDATED); behaviour differences
(AI choices, positions) make per-class ratios noisy, so the owner's visual check stays decisive.

## Suggested owner test order (Pokitaru)

1. The latest owner session used IG-v16f. Check the actual loaded build and plugin
   enablement before testing; later owner work disabled InterpGate. Record a clean
   A0 baseline with the monitor (above) near the crabs.
2. `fixes.py --target C1 --fix nav,nav2` -> crabs and training bots move normally?
3. From a clean boot: `fixes.py --target C1 --fix nav,nav2,crab,crabtimers,telemetry` (the
   quarantined `timer-patches.py --class Crab` batch stays off). Attack rhythm, recovery and
   cooldown as in A0?
4. Review TrainingBot's generated list before enabling it near the training area.
5. `fixes.py --target C1 --fix nav,nav2,frametimers` -> Help reminders, teleporter,
   enemy waves (delay between waves) at original pace? Anything slower than A0?
6. `fixes.py --target C1 --fix nav,nav2,cows` where mutant cows / Agent of Doom appear.
7. `fixes.py --target C1 --fix laser` -> LaserTracer ammo drain and beam timing vs A0.
8. `--fix waterfall,particles` facing the waterfall; then `particles-all` (crates, fire, sparks).
9. `--fix phases,clock` (HUD fades, ocean sound, Polarizer, skill point window).
10. `--fix pathanimals,springs,luna,spawn,laserbeam` (turning, doors, Luna, particle density, laser beam);
    `--fix pathanimals` near walking animals, `crank` on the crank bolts, `elevator` before
    riding the elevator, `boatfade,frames30` on the boat.
Use `--target A0` (and `timer-patches.py --target off`) to compare with the original.

- `camera` (added later): manual camera yaw/pitch input accel, damping and caps use literal 1/30 once per call; at C1 it turned 2x too fast (owner). 3 `lui` words 0x3D08 -> 0x3C88 at 0x308C/0x361C/0x37E0 (STATIC_CANDIDATE, untested). Test L/R and D-pad up/down speed vs original30.

- `campos` (Priority 2, optional): default follow-camera distance 5.0 -> 9.0 (`0x2AA3F0`) and height 1.14 -> 1.90 (`0x2AA3FC`); `--cam-distance/--cam-height` override. Legacy owner-validated profile on Pokitaru (visual, legacy session); not a measured PS2 reference. Source constants are copied at camera init (`0xCA24`), so it applies at the next level load. Test: combat, aiming, tight walls (collision shortening `0x9444`), other levels (level data may override).
- `fov` (Priority 2, optional): `--fov-rad X` writes the vertical FOV constant `0x2AA3C0` (vanilla 0.5498). No default: PS2 FOV UNKNOWN; legacy decision kept FOV vanilla. Cutscene cameras use their own FOV.
- `camera` update: now also covers the follow-yaw assist `0x7740` (4 `lui` branch copies 0x79B8/0x7AA4/0x7AF0/0x7B38 -> 1/60, gain `0x2AA500` 0.6 -> 0.3675 = 1-sqrt(0.4) to keep the same per-second convergence). 8 words total, STATIC_CANDIDATE.
- Open camera parity items (UNKNOWN, not patched): per-call second-order smoothing filters `0x7C64`, `0x4C84`, `0x804C`, `0x1424`/`0x14A8` (constants `0x2AA430-0x2AA4F4`, e.g. 0.9512, 0.6065, 0.8465) and the camera history ring in `0xAA44` (`0x2AA5DC`=15 frames x 1/30). At C1 they run twice per second-equivalent, so the camera likely lags less than original30. An exact correction needs coefficient re-derivation or a step-response measurement (A0 vs C1) first; do not guess.

- `tools/runtime/loading-fps.py` (Priority 2, optional, separate script; EBOOT-resident, no plugin needed): 4 words: interval `0x088410B8` 3.0 -> 1.0, delta `0x088410BC` 0.05 -> 1/60 (stored, NOT recomputed per frame), vblank wait `jal` at `0x0880727C` -> nop (limiter has its own entry wait; floor was 2 vblanks = 30 FPS), fade literal `0x08807230` 20 -> 60. Modes on/off/status/watch. OWNER-OBSERVED 2026-10-01 (no plugin, level load incl. other than Pokitaru): loading screen 60 FPS, duration and animation speed match vanilla (1:1), game stable. Not measured with a stopwatch. EBOOT states 3/4 are the load (watch log). Spinner counter 0x088410C4 is frame-based (cosmetic). Note: with InterpGate active a load of another level crashed PPSSPP once (cause UNKNOWN, not investigated).
- `loading-fps.py --group ribbon,s4,s0,s2` (optional, INFERRED/untested): per-frame particle/ribbon data written for 20 FPS (life x3, drift /3, emission /3, state-3 ribbon spin /3; 10 words, none shared). Reason: the Inside Clank loading screen (Ratchet shrink loop, fall/spin on exit) is still 3x too fast with the base patch. See research/inbox/eboot-loading-anim-static-20261001.md for the live test order (state mapping must be confirmed first).
