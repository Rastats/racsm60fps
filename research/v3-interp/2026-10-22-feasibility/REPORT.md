---
kind: feasibility
title: "Render interpolation between two logic states: feasibility on LEVEL_01 (Pokitaru)"
date: 2026-10-22
authors: ["Claude (Opus 5.5)"]
status: complete
evidence: [OBSERVED, INFERRED, UNKNOWN]
systems: [timing, rendering, entities, interpolation]
levels: [Pokitaru]
variants: [A0, C1, G1]
related: [research/v2/framerate-methods-20261006/REPORT.md, research/live-tests/pokitaru/session-2026-09-30/SESSION-LOG.md, tools/runtime/pump-gate.py]
summary: "Pure 60 Hz logic + interpolation: refuted (nothing to interpolate under C1). Hybrid G1 (world entities of pump 1 at 30 Hz, player/camera/animation at 60 Hz) + render-only interpolation: feasible on LEVEL_01: debugger prototype OBSERVED (correct world speed, 238/239 drawn changes, game state bit-identical); PRX (1.8 KB code, 46.8 KB resident) OBSERVED running the same gate and blend, its speed and no-leak INFERRED. Owner must rule on the 30 Hz world logic."
---

# Render interpolation between two logic states (exploratory)

> Exploratory study requested by Antoine. The owner (Linkinito) has not given
> an opinion and rejects "30 Hz logic / 60 Hz display". This note tests an
> idea, it does not propose a direction.

**Verdict.**
1. "60 Hz logic + interpolation" as such: refuted. Under C1 every system
   already advances once per displayed frame; there is no in-between state.
2. Hybrid feasible on LEVEL_01: world entities of pump 1 at their original
   30 Hz (G1), player, camera and skeletal animation at 60 Hz, world
   transforms blended in the render pass only. The debugger prototype
   (OBSERVED) brings world speed back to A0 (1.4926 against 1.4985 u/s),
   changes drawn positions on 238/239 frames and leaves the game state
   bit-identical to G1. The PRX (1.8 KB code, 46.8 KB resident) runs the same
   gate and blend on the bench (OBSERVED: counters, 59.94 Hz kept); its speed
   and no-leak results are INFERRED from the shared logic, not measured.
3. It is still 30 Hz world logic, which the owner rejects today: the owner's
   call.
4. Open: real PSP CPU cost (estimated 1-4 % of a frame pair), platforms the
   player rides, the Blaster cooldown, other levels (engine signatures found
   in all 20 level modules, not run).

## What the idea can mean

Interpolating between two logic states only produces new images where a state
advances less often than the display. Under C1 the player, camera and group
pump 1 already advance once per 59.94 Hz vblank, so between two displayed
frames there is no intermediate state to draw.

The variant that leaves something to interpolate is a hybrid: player, camera,
input and weapons stay at 60 Hz (C1), the world entities of group pump 1 keep
their original 30 Hz cadence (G1 gate, `tools/runtime/pump-gate.py`), and
their transforms are blended during the render pass only. World entities
still tick at 30 Hz: that is the point the owner has to rule on.

## Static map of one gameplay frame (LEVEL_01, module RVAs, OBSERVED by disassembly)

| Step | RVA | Role |
| --- | --- | --- |
| Frame dispatcher | `0x159DC` | state switch (jump table at `0x1C02C8`); gameplay case calls update then render |
| Update | `0x1517C` (call `0x15AA8`) | delta `0x151E0`, player chain `0x2FFF0`, pump 1 `0x6B7F4` (call `0x15230`), pump `0x6B618`, camera matrices `0x24A7C` + `0x8DCE4`, particles `0x8CC18` |
| Render | `0x156DC` (call `0x15AB0`) | display list start `0x1506C`, scene `0x15400`, HUD/overlays, end of frame `0x94970` |
| End of frame | `0x94970` | GE finish/sync, `0x96490` flip with the VBlank waits (`0x96650` is the C1 nop site) |
| Render without update | `0x262AC` (call `0x15AD8`), `0x15B98` path | draws the scene from the current state with no pump-1 update |

Draw queues: pump 1 resets three per-frame counters at entry (`0x6B84C..0x6B864`,
segment-relative `0x3B28`, `0x3BEC`, `0x3CB0`). Entity callbacks refill them
during update. The render pass consumes them: `0x6BB14(pass)` walks records
`[arg, fn, pass]` (12 bytes, base `0x3BF0`) and calls `fn(arg)`; `0x6BB9C`
walks records consumed by `0x72AD0(matrix, model, mask)`.

This is why mode G (skip some entity callbacks) emptied lists and made the sea
flicker on 2026-09-30, while G1 (skip the whole pump, counters not reset)
did not.

## Live tests (2026-10-22)

Setup: portable PPSSPP 1.20.4 (`emu/ppsspp-3`, port 60909), IR interpreter
core (`CPUCore = 2`), Direct3D 11, no plugin, state `pokitaru-start` (A0) and
`interp-g1` (the same spot with G1 applied by `tools/runtime/pump-gate.py`).
No input during the runs. Times are emulated (`cpu.status.ticks`, 222 MHz).
Scripts: [scripts/](scripts/). Raw runs: `work/runs/interp-0xx` (outside Git).

Debugger caveat found on the way: with several CPU breakpoints added in a row,
only the last one fired until a `cpu.breakpoint.list` request was sent after
the adds (OBSERVED on both the JIT and IR cores; cause UNKNOWN).
`render_probe.py` sends that round trip.

### Dispatcher case (OBSERVED)

60 gameplay frames under A0: the update `0x1517C` was entered 60 times from
`0x15AA8` and the render `0x156DC` 60 times from `0x15AB0`; no other caller.

### 1. The draw reads the entity world matrix live (OBSERVED)

Pump-1 entity records start with a 4x4 world matrix: rows 0-2 rotation, row 3
translation and 1.0 (Ratchet's moby, group 62: rotation rows match a yaw, row 3
equals the player position). `render_probe.py lift` adds 1.5 u to row 3 x at
render entry and restores it after the render call, for 20 frames. The window
capture shows Ratchet's body displaced while Clank, a separate entity
(group 67), stays in place; the value written was still in memory at render
exit (the render pass does not rebuild the matrix from another source), and
the restored value is the original bit for bit.

### 2. The render pass writes nothing in entity state (OBSERVED, scoped)

Write memchecks armed only between render entry and exit, over the whole
pump-1 entity area (`0x18000` bytes from the first entity array), Ratchet's
animation block (`+0x48`) and data block (`+0x58`): 0 writes in 30 frames.
Positive control, same ranges armed during the update only: the 200-hit cap
was reached in the first frame (store at `0x0E2EC`). Scope: these ranges
only; global render-side caches elsewhere in RAM are not covered by this test
(see the leak test below for an end-to-end check).

### 3. Skinning matrices are computed in the update, outside pump 1 (OBSERVED)

The moby draw `0x6F514` loads the world matrix from the moby itself and draws
the skinned model with a bone-matrix buffer at `moby+0x50` (call `0x7598C`).
Write memchecks on Ratchet's bone buffer: 0 writes during the render pass in
10 frames; during the update, stores at `0x77978` (cap of 2000 hits reached
in under 2 frames). `0x77978` belongs to the animation pass reached from
`0x78158`, which the main update calls once per frame after pump 1. So under
G1 skeletal poses still advance at 60 Hz; only what pump-1 callbacks write
(the world matrix and the AI state) is at 30 Hz.

Population at the Pokitaru start: 1,162 entity slots in 155 groups, 465
active, 6 active with a bone buffer; about 14 entities move per 30 Hz tick
(1,683 blended matrices over 120 ticks).

### 4. Prototype G1 + render interpolation (OBSERVED)

`interp_proto.py --mode interp`: at render entry on frames where the gated
pump ran, every pump-1 world matrix that changed since the previous logic tick
is replaced by `lerp(previous, current, 0.5)`; after the render call the exact
entry bytes are written back. On frames without a pump run the current state
is drawn. Entities that move on a frame without a pump run are driven at
60 Hz elsewhere and are never blended: the prototype found four, Ratchet's
moby and the three entities attached to him (groups 62, 67, 68, 80).

Same tracked entities, about 4 emulated seconds each:

| Config | Entity 16:0 speed (u/s) | Drawn position changes per render |
| --- | --- | --- |
| A0 | 1.4985 | 119/119 at 29.97 Hz |
| C1 | 2.9969 (x2.00) | 239/239 at 59.94 Hz |
| G1 | 1.5043 | 120/239 (30 Hz steps of 0.050 u) |
| G1 + interpolation | 1.4926 drawn, 1.4926 authoritative | 238/239 (steps of 0.025 u) |

Entity 40:3: A0 3.0076, C1 6.0022, G1 3.0174, G1 + interpolation 2.9939 u/s;
drawn steps 0.100 u at 30 Hz in G1 against 0.050 u every frame with
interpolation. Speeds differ by up to 0.4 % between runs because the windows
start at different points of a curved path; C1's factor of 2 is the known
defect.

The world entities are drawn one 60 Hz frame later than their logic state.
Player, Clank, camera and skeletal animation are not delayed.

### 5. No leak into the game state (OBSERVED)

Digest (SHA-1) of the whole entity area (`0x24500` bytes) at every render
entry, before any blend, matched on the gate's run counter between two runs
started from `interp-g1`:

| Pair | Matched renders | Identical |
| --- | --- | --- |
| G1 vs G1 (determinism) | 238 | 238 |
| G1 vs G1 + interpolation | 237 | 237 |
| G1 vs G1 + interpolation with 60 Hz exemption | 238 | 238 |

The interpolation changes what is drawn, not what the game simulates.

### 6. What the screen shows (OBSERVED)

Window captures after each render, G1 against G1 + interpolation from the same
state (`scripts/make_strip.py`, GIFs in `work/runs/interp-035-seagull-crop.gif`
and `interp-036-full.gif`, outside Git): the two runs are pixel-identical on
frames without a pump run, and on pump frames they differ only in a 45 x 20
pixel box around a seagull at the right edge, which moves by half a step. The
camera turns every frame in this state, so judder is better read from the
logged drawn transforms than from pixel differences.

### 7. PRX prototype InterpRender (OBSERVED, cost INFERRED)

[prx/interp_render.c](prx/interp_render.c) moves the debugger prototype into
a PSP plugin: same G1 gate (`ir_pump`, pump 1 every second update with the
accumulated delta), same snapshot / blend / restore around the render
(`ir_render`), same 60 Hz exemption (an entity whose matrix changes on a frame
without a pump run is never blended again). No libc, no thread, no imports;
it does nothing until [scripts/ir_apply.py](scripts/ir_apply.py) writes its
config and redirects two LEVEL_01 call sites (`0x15230` jal pump 1,
`0x15AB0` jal render) plus the C1 core words. Built with
`pspdev/pspdev:v20261001` (digest
`sha256:54895e6f5afb71b8f4f6915ee6d5023e1e087ca7afdf2dcb1d7a694a5233e45f`)
by [prx/build.sh](prx/build.sh); build outputs stay outside Git.

| Item | Value |
| --- | --- |
| Code | 1,828 B `.text` |
| Data | 44,488 B `.bss` (640 snapshot entries, 160 restore slots, exemption bitmap) |
| Resident module | 0xB700 B (46.8 KB) at `0x08957100` in PPSSPP |

Bench: PPSSPP 1.20.4 IR core, plugin loaded from
`memstick/PSP/PLUGINS/InterpRender`, new game to the Pokitaru start, state
`interp-ir-pokitaru` (base `0x09144D00`). The state holds build IR-v1, whose
exemption test compared `hash | 1` with `hash` and exempted 211 of 253
entities. The source is fixed (IR-v2); the bench applies the same fix to the
resident IR-v1 as one word (`ori v1,v1,1` at module offset `0x37C` -> nop,
guarded), runs `work/runs/interp-070..074`:

| Counter (mode 2, gate + interpolation) | Value |
| --- | --- |
| Pump runs / skips | 374 / 375 |
| Frames with a blend / matrices blended | 210 / 2,096 (10 per blended frame) |
| Entities exempted as 60 Hz | 4 (same count as the debugger prototype; slots not compared) |
| Snapshot entries | 460 |
| Snapped (jump > 4 u), overflows | 0, 0 |

Frame period over 119 frames, render exit to render exit: mean 3,703,700
ticks (59.94 Hz) in mode 1 and mode 2, min 3,671,696, max 3,735,704; render
exit stays at the same vblank phase (mean 3,547,595 ticks in mode 1 against
3,548,363 in mode 2). Render exit is pinned by the vblank wait inside the render, so this shows that no frame slipped in emulated time, not what the plugin costs.

Cost. The breakpoint-based [scripts/cost_probe.py](scripts/cost_probe.py)
did not measure it: with six CPU breakpoints only the last-added one fired,
even with a list round trip after each add (runs `interp-051/053/071/073`).
PPSSPP's emulated cycle count would not price cache misses anyway. Static
estimate from the code (INFERRED): per pair of frames, a scan of 1,162 slots
(~10 instructions each), then for 460 active entries a 12-float copy, two
FNV hashes and one compare pass, about 120k instructions, plus ~2,800 data
cache misses over 128-byte records. On a 333 MHz Allegrex that is 0.4 to
1.2 ms against 33.4 ms, so 1 to 4 % of a frame pair. Real-hardware headroom
under C1 is UNKNOWN; the scan can be cut by hashing only entities that
moved and by dropping the hash once the exemption set is stable.

## Expected gain (against C1 on LEVEL_01)

- World speed: correct by construction for every pump-1 class, measured on
  two entities (16:0 and 40:3, both within 0.4 % of A0, C1 at x2.00).
- Fix catalogue (INFERRED from `docs/FIX_CATALOGUE_2026-10-01.md`): about 16
  of ~37 rows target pump-1 classes and would no longer be needed: nav, nav2,
  cows, crab, crabtimers, TrainingBot, elevator, boatfade, age70, butterfly,
  firerate, pathanimals, springs, luna, crank, waterfall. Not covered and
  still needed: camera, camfilters, particles, weapons, HUD, frame clock,
  spawn, physstep.
- Motion: world entities drawn on 238/239 frames in half steps instead of
  120/239 under plain G1, so G1 loses its judder.

## Risks

- 30 Hz world logic: AI, collisions between world entities and their timers
  update at the original rate. Inputs that pump-1 objects read (shops,
  teleporters, switches) are sampled at 30 Hz.
- Platforms the player rides (boat, elevator): the platform is drawn half a
  step behind its logic while the player is drawn at 60 Hz on top of it.
  The boat broke under an earlier G mode; not tested here.
- Classes split between pump 1 and the 60 Hz chain: on 2026-09-30 the Blaster
  cooldown got longer under G1 and LaserTracer stayed x2.
- Child entities and anything placed relative to a pump-1 matrix outside the
  entity record are not blended; spawns and teleports rely on the 4 u snap.
- One 60 Hz frame of display delay for world entities (not for the player or
  camera).
- An exception that keeps one pump-1 class at 60 Hz needs its callbacks run
  on the skipped frame and its draw records replayed: not designed.
- Memory: 46.8 KB resident module against a history of memory-pressure
  crashes on hardware.
- Only LEVEL_01 was run. [scripts/engine_signatures.py](scripts/engine_signatures.py)
  finds the draw-queue walker, the moby draw and the pump-1 dispatch in all
  20 LEVEL_xx modules (not in FRONTEND), so the method should carry over;
  each level still needs its call sites and manager offset.

| Module | drawq / drawmoby / pumpcb (RVA) |
| --- | --- |
| LEVEL_01 | 0x6BB5C / 0x6F534 / 0x6B9B0 |
| LEVEL_02 | 0x71A2C / 0x755AC / 0x71880 |
| LEVEL_03 | 0x6B6F0 / 0x6F200 / 0x6B544 |
| LEVEL_04 | 0x6E988 / 0x7251C / 0x6E7DC |
| LEVEL_05 | 0x69B18 / 0x6D654 / 0x6996C |
| LEVEL_06 | 0x66A90 / 0x69BD4 / 0x668E4 |
| LEVEL_07 | 0x6D538 / 0x70F78 / 0x6D38C |
| LEVEL_08 | 0x73398 / 0x76F94 / 0x731EC |
| LEVEL_09 | 0x68830 / 0x6C244 / 0x68684 |
| LEVEL_10 | 0x6BEE4 / 0x6F924 / 0x6BD38 |
| LEVEL_15 | 0x5491C / 0x586D4 / 0x54770 |
| LEVEL_16 | 0x5D7C8 / 0x61100 / 0x5D61C |
| LEVEL_17 | 0x5D47C / 0x60D74 / 0x5D2D0 |
| LEVEL_18 | 0x5D6F0 / 0x60FE8 / 0x5D544 |
| LEVEL_19 | 0x5EDA8 / 0x626A0 / 0x5EBFC |
| LEVEL_20 | 0x52994 / 0x557A4 / 0x527E8 |
| LEVEL_21 | 0x5491C / 0x586D4 / 0x54770 |
| LEVEL_22 | 0x5FCC0 / 0x62C50 / 0x5FB14 |
| LEVEL_23 | 0x63E20 / 0x66E90 / 0x63C74 |
| LEVEL_24 | 0x6637C / 0x6946C / 0x661D0 |

## Why this is not "30 Hz logic / 60 Hz display"

The rejected scheme runs the whole game at 30 Hz and shows each image twice
or interpolates everything, including the player and the camera, so input
latency and camera motion stay at 30 Hz. Here the player, camera, input,
weapons and skeletal animation keep the patch's 60 Hz; only the world
entities of pump 1 return to the rate their code was written for, and only
their drawing is interpolated. It is a split by system, not a split between
logic and display. The world AI still ticks at 30 Hz, so it remains the
owner's decision whether that is acceptable.

## Questions for the owner

1. Would world entities of pump 1 at 30 Hz, with player, camera and animation
   at 60 Hz and interpolated drawing, be acceptable to you?
2. Is the "30 Hz island" of InterpGate IG-v24 a similar mechanism, and could
   its sources be shared?
3. Which pump-1 classes interact with the player at 60 Hz in your experience
   (Blaster cooldown, projectiles, platforms, shops, teleporters)?
4. Could you share a savestate on the boat or an elevator, to test a platform
   the player rides?
5. What CPU headroom does the 60 FPS patch leave on real PSP hardware?
