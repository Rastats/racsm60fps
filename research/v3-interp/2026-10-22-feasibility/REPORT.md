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

## Open questions (live tests below)

1. Does the render pass read entity transforms live, or a copy made during update?
2. Does the render pass write state that the next update reads?
3. Are skinning/pose matrices computed during update or render?

## Results

(pending)
