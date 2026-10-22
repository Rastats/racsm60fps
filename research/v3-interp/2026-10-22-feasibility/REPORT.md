---
kind: feasibility
title: "Render interpolation between two logic states: feasibility on LEVEL_01 (Pokitaru)"
date: 2026-10-22
authors: ["Claude (Opus 5.5)"]
status: in-progress
evidence: [OBSERVED, INFERRED, UNKNOWN]
systems: [timing, rendering, entities, interpolation]
levels: [Pokitaru]
variants: [A0, C1, G1]
related: [research/v2/framerate-methods-20261006/REPORT.md, research/live-tests/pokitaru/session-2026-09-30/SESSION-LOG.md, tools/runtime/pump-gate.py]
summary: "Work in progress. Static map of the frame: update 0x1517C, then render 0x156DC, then end of frame 0x94970; entities queue draw records during update."
---

# Render interpolation between two logic states (exploratory)

> Exploratory study requested by Antoine. The owner (Linkinito) has not given
> an opinion and rejects "30 Hz logic / 60 Hz display". This note tests an
> idea, it does not propose a direction.

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
