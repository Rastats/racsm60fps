---
kind: live
title: "Kalidon skyboard (LEVEL_22): speed/slow volumes under C1, the climb floor and the `slope` fix"
date: 2026-11-08
authors: ["Claude (Opus 5.5)"]
status: done
evidence: [OBSERVED, INFERRED]
systems: [skyboard, movement, tooling]
levels: [Kalidon Skyboard]
variants: [A0, C1+boardtimers+racecount+aimove+racetime, C1+boardtimers+racecount+aimove+racetime+slope]
environment: "Bench instance emu/ppsspp-1, port 60907 (PPSSPP 1.20.4), worktree wt-slopefix; offline reading of LEVEL_22.PRX (capstone)"
supersedes: [research/live-tests/2026-10-24-skyboard-slope/REPORT.md]
related: [research/live-tests/2026-10-24-skyboard-ai/REPORT.md, research/live-tests/2026-10-23-skyboard/REPORT.md, tools/bench/levels.py]
summary: "Cause: the speed/slow volume entities set a brake/accelerate event once per frame and the board speed spring (0xDAC4, per substep, no delta) uses it on the next substep only; A0 brakes on 1 substep of 2, C1 on every one, hence the climb floor HUD 3.00. Fix `NATIVE['LEVEL_22']['slope']`: 3 data words (k 0x222324, brake 0x22231C, accelerate 0x222318) refitted by simulation. Full race C1+fix+slope look 14: climb 2.17 s on 3 laps of 3 (A0 2.10-2.33, C1+fix 2.83), HUD min 4.14, race won (Best Times 3 : 15). board_probe straight / right turn identical, left turn closer to A0. Trade-off: one brake-ground patch (surface type 3) shares the words, estimated +0.18 s per lap for the player."
state: "work/states/slopefix-c1-climb (+ .json sidecar): C1+fix, 1 s before the climb, saved while stopped at a frame break"
---

# Kalidon skyboard, 2026-11-08: the climb floor and the `slope` fix

1. **Cause (OBSERVED):** speed/slow volumes set an event once per frame; the per-substep speed spring uses it on one substep. A0 brakes on 1 substep of 2, C1 on all, so C1 floors at HUD 3.00 on the climb.
2. **Fix:** `C1+slope`, three data words of the spring's target block refitted so one C1 substep equals an A0 pair (`scripts/springsim.py`).
3. **Result (OBSERVED, full race look 14):** climb 2.17 s on 3 laps of 3 (A0 2.10-2.33, C1+fix 2.83), HUD minimum 4.14, race won (« Learner's Permit 3 : 15 »).
4. **Non-regression:** `board_probe` straight and right turn identical; left turn moves toward A0.
5. **Trade-off (ESTIMATED):** one LEVEL_22 brake-ground patch shares the words: about +0.18 s per lap for the player. Bench: paused state loads (README pitfalls 29-30).

## 1. Cause (OBSERVED)

The board speed x = player+0x230 (per substep; the HUD shows the step length +0x264 x 30) follows a
spring run once per substep, with no delta (0xDAC4, called at 0x4A4DC):

```
v = k (T - x) - 0.2 v      (v = player+0x238, clamped by +0x244)
x = x + v
```

The target block 0x4A190..0x4A4C8 sets T and k each substep:

| Case | T | k |
|---|---|---|
| normal | t = 0.3333 blended to 0.14 by the pitch, +0.1667 with boost | 0.02 |
| accelerate (0x476D8(1)) | t + 0.2667 (0x222318) | 0.1 (0x222324) |
| brake (0x476D8(2), board mode) | t x 0.3 if t >= 1/3 (0x22231C = -0.2333), else t - 0.2333 | 0.1 |

0x476D8(n) is true when the event byte G+0x159 == n, or when the ground class G+0x158 == n and no
event is pending (G = RAM 0x940CC98, PRX 0x2D2F98). The accelerate and brake branches then clear the
event (`sb zero,0x159(G)` at 0x4A3B0 / 0x4A450).

The event is set by the speed/slow volume entities: 0xF14C4..0xF14F0 tests the player inside the
volume's box (local coordinates in [-1, 1]) and in board mode (player+0x100 == 2), then calls
0x475C8 (event 1, volume flag +0x10C set) or 0x475DC (event 2). That update runs once per frame.

- A0: 2 substeps per frame. The first brakes (T = 0.1, k = 0.1) and consumes the event; the second
  is normal (T = 0.3333, k = 0.02). Runs `slopefix-a0-climbwatch` v384-388: stores at 0xDB20
  alternate between the two targets.
- C1: 1 substep per frame, the volume sets the event every frame, so every substep brakes
  (`slopefix-c1-climbwatch` v292-294). The speed settles on T = 0.1: HUD 3.00, the floor seen on
  2026-10-24.
- A0 cycle steady state 0.137 (HUD 4.12, spring simulation) against the measured plateau
  4.07-4.25.

Ruled out: the pitch spring G+0x68 (its C1 target came from a state-load artefact, the G+0x1A0
timer, and it is 0 during the climb); the +0x264 stores 0x337C0 / 0x33A64 / 0x34788-0x34808.

The ground class G+0x158 (ground probe 0x46AA0: surface type 5 -> 1, 3 -> 2, at 0x4AAF4, 0x4ADA0,
0x4AFA4 and their brake twins) is written every substep, so ground-driven braking or accelerating
is already per substep in both configs.

## 2. Fix (`NATIVE['LEVEL_22']['slope']`, three data words)

The three constants are read only by this block (checked: 0x222324 at 0x4A3A0 / 0x4A440,
0x22231C at 0x4A410 / 0x4A430, 0x222318 at 0x4A390). One C1 volume substep must give what an A0
pair (volume substep + normal substep) gives. `scripts/springsim.py` fits:

- B and A on the A0 cycle steady state (linear in t: the same B fits both brake branches);
- then K on the distance covered in the first second, for entry speeds t, 0.26 (the measured climb
  entry) and 0.45.

| Word | A0 | slope |
|---|---|---|
| 0x222324 k | 0x3DCCCCCD (0.1) | 0x3D8068DC (0.0627) |
| 0x22231C brake | 0xBE6EEEF0 (-0.2333) | 0xBE48CE3A (-0.1961) |
| 0x222318 accelerate | 0x3E888889 (0.2667) | 0x3E657DEA (0.2241) |

Simulated (HUD at 0.25 / 0.5 / 1 / 4 s, brake volume at t = 1/3): A0 6.66 / 5.23 / 4.35 / 4.12,
C1 4.83 / 3.46 / 3.04 / 3.00, C1+slope 6.67 / 5.21 / 4.34 / 4.12; distance over 1 s 11.64 / 8.55 /
11.65. Accelerate volume: C1 covered 33.08 u in 1 s against 29.56 in A0 (+12 %), C1+slope 29.55.
A one-frame volume touch differs by 1.2 % in distance over 2 s.

Because the words are shared with the ground class path, ground of surface type 3 or 5 drifts from
A0 under C1+slope (on a long stretch it would brake to HUD 4.1 where A0 brakes to 3.0). LEVEL_22 has
one such patch (OBSERVED, `slopefix-race-c1slope` with a change-only watch on G+0x158,
`scripts/surfaces.py`): brake ground (class 2, writer 0x4ADBC / 0x4AB10) at (-21, 13.7, -126), 9-10
vblanks per lap, entered at HUD 11.2; no accelerate ground (class 1) in the race. Simulated cost
(`springsim.py`, 10 brake-ground substeps, entry HUD 7.8 / 12.0): C1+slope covers +2.6 / +4.0 u
more than A0 over the next 3 s, i.e. about +8 / +12 vblanks, so roughly 0.18 s per lap and 0.55 s per
race in the player's favour (ESTIMATED, not measured). Removing it needs a code change that picks
the volume constants only on the event branch, on relocated `lui` pairs (README pitfall 23): left out.

## 3. Bench changes

- `tools/bench/states.py`: `save` writes `<name>.json` (CPU ticks around the save; called with the
  stopped Debugger of a frame break, the state is that exact instant); `load` raises unless the
  emulated clock jumps (a silent non-load produced the invalid run `slopefix-a0-surf`), and
  `load(pause=True)` leaves the CPU stopped at the loaded instant. README pitfall 29.
- `tools/bench/breakloop.py`: a stale `cpu.stepping` broadcast from the paused load is no longer
  taken for a break ("is not a store" at 0x08805774, `slopefix-smoke-arrive`). README pitfall 30.
- `scripts/rec.py`: `--watch-player`, `--regs` (FPU registers at each watched store), save inside
  the frame break (`--save-at`), paused load. Check: `slopefix-c1-climb-check2` starts at
  (92.54, 18.96, -118.48), the saved position, raceFrames 1681 -> 1980 in 5 s; the run before the
  change (`slopefix-c1-climb-check`) started 6 s further on.

## 4. Measurements

Full race from `banc-skyboard-arrive`, look 14 (`scripts/race.sh ... --look 14 --watch 940CDF0`),
climb box x 100-120, z -118..-103, times from GO (`scripts/climb.py`):

| Run (config) | Climb lap 1 / 2 / 3 | HUD min, mean |
|---|---|---|
| `banc-skyaward-a0-watch` (A0, 2026-10-24) | 2.33 / 2.10 / 2.10 s | 4.07-4.10, 4.86-5.57 |
| `banc-skycont-look14` (C1+fix, 2026-10-24) | 2.83 / 2.83 / 2.83 s | 3.00, 4.02-4.04 |
| `slopefix-race-c1slope` (C1+fix+slope) | 2.17 / 2.17 / 2.17 s | 4.14, 5.26-5.28 |

- Climb in the A0 range on 3 laps of 3, HUD 3.00 floor gone (minimum 4.14, A0 4.07-4.10) (OBSERVED).
- Race won (OBSERVED, `work/runs/slopefix-race-c1slope/fin-v16638.png`): « Best Times: Learner's
  Permit 3 : 15 », « Prize: Bolts: 750 ». raceFrames froze at 11707 (195.1 s at 60/s; the menu
  shows A0 units through `racetime`). The continuous C1+fix race of 2026-10-24 was lost.
- Splits (`scripts/splits.py`, last point of AI 0's line): C1+slope 195.7 s, C1+fix 209.6 s, A0
  202.5 s. Respawn events (rec.py): A0 2 (107.0 and 113.0 s from GO), C1+fix 3, C1+slope 0, so
  the 7 s ahead of A0 comes mostly from respawns, not from a speed excess of the fix (INFERRED; the
  brake ground estimate above is 0.55 s).
- The surface watch logged 6 changes (3 brake-ground passes); the watched word also holds the event
  byte, whose stores fall outside the exact watch address and are not logged.

`board_probe` from `banc-skyboard-arrive`, 2 repeats each, all repeats identical (OBSERVED,
`work/runs/slopefix-probe-straight`, `-turn`, `-turn-a0`; path in u from GO):

| Script | t | A0 | C1+fix | C1+fix+slope |
|---|---|---|---|---|
| straight | 4.9 s | (not rerun) | 99.77 | 99.77 |
| turn right | 4.9 s | (not rerun) | 93.69 | 93.69 |
| turn left | 3.0 s | 58.24 | 57.71 | 57.71 |
| turn left | 4.0 s | 80.63 | 83.48 | 81.63 |
| turn left | 4.9 s | 105.40 | 106.35 | 102.86 |

- Straight and right turn: identical with and without `slope`, every metric (no volume on those lines).
- Left turn: the line crosses a speed volume between 3.0 and 4.0 s. There `slope` brings C1 back
  toward A0 (gap at 4.0 s +2.85 u -> +1.00 u). By 4.9 s the A0 and C1 lines have split on heading
  (151-156° in A0 against 144-147° in C1 from 3.0 s, the heading gap handled by the sister session
  « rotation de 7° en trop »), so 4.9 s does not compare the speed term.

## Files

- `scripts/springsim.py` (new): spring simulation and fit of the three words.
- `scripts/surfaces.py` (new): ground class G+0x158 changes over a run.
- `scripts/prxdis.py` (was `dis.py`, renamed: it shadowed the stdlib `dis` that capstone imports),
  `watchlog.py`, `speedsteps.py`, `fcdiag.py`, `bplist.py`, `ramaddr.py`, `loadtrace.py` (new
  diagnostics); `climb.py`, `splits.py`, `seg.py`, `refs.py`, `aiwriter.py`, `race.sh`, `rec.py`
  copied from 2026-10-24 with the bench path set to this worktree.
- Raw runs `work/runs/slopefix-*` and states `work/states/slopefix-*`, not committed (game-derived).
