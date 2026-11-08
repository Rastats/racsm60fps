---
kind: live
title: "Kalidon skyboard (LEVEL_22): player slope term under C1 — partial, stopped 22:49"
date: 2026-10-24
authors: ["Claude (Opus 5.5)"]
status: partial
evidence: [OBSERVED, INFERRED, UNKNOWN]
systems: [skyboard, movement, tooling]
levels: [Kalidon Skyboard]
variants: [A0, C1+boardtimers+racecount+aimove+racetime]
environment: "Offline reading of LEVEL_22.PRX (capstone) and of existing runs under work/runs; one bench launch (instance ppsspp-1, port 60907) whose debugger never answered"
supersedes: []
related: [research/live-tests/2026-10-24-skyboard-award/REPORT.md, research/live-tests/2026-10-23-skyboard/REPORT.md, tools/bench/levels.py]
summary: "Partial, stopped 22:49 (session closed by Antoine at 23:23). From the existing runs: the climb (100-120, 19.5-21, -118..-103) takes 2.83 s in C1+fix on all three laps against 2.10-2.33 s in A0, and the C1 HUD sits at exactly 3.00 for 0.8 s where A0 levels at 4.07-4.25. The HUD is player+0x264 x 30.0 (0x46A50-0x46A60), so player+0x264 is the board speed per 1/60 s and the C1 floor is 0.1. 13 static stores to +0x264 listed; the slope term itself is not located, no fix word was added, nothing was measured live."
state: "none saved (fin-slope-c1-preclimb was not created)"
---

# Kalidon skyboard, 2026-10-24 late evening: player slope term (partial)

**Partial, stopped 22:49.** The session was closed by Antoine at 23:23 before any live measurement.

1. **Gap confirmed on the existing runs (OBSERVED):** climb box 2.83 s in C1+fix on laps 1-3 (`banc-skycont-look14`) against 2.33 / 2.10 / 2.10 s in A0 (`banc-skyaward-a0-watch`), +21 to +35 %; HUD minimum 3.00 in C1 (flat for ~0.8 s) against 4.07-4.10 in A0.
2. **Speed word (OBSERVED, static):** the HUD setter 0x92F84 is called once, at 0x46A5C, with `player+0x264 x 30.0` (`lwc1 f12,0x264(s0)` at 0x46A50, `lui 0x41F0` at 0x46A54). +0x264 is therefore the speed per 1/60 s (HUD = speed / 2 in u/s), and the C1 floor is +0x264 = 0.1.
3. **Shape (INFERRED):** A0 decays to a plateau of 4.1-4.25 on the slope (an equilibrium of drive against slope); C1 decays faster (7.54 → 3.98 in 0.4 s, A0 5.54 → 4.22 in 0.5 s) and stops at exactly 3.00, which looks like a floor clamp of 0.1 per substep reached because the slope pull wins in C1.
4. **Not done:** the writer of the slope term, the `slope` fix word in `levels.py`, every A0 / C1 / C1+slope measurement, straight / turn non-regression and the full race. The success predicate is not evaluated.
5. **Next step:** write breakpoint on player+0x264 on the climb (state saved before the climb, see below), keep the writes whose value falls on the slope, read the term at that PC with `dis.py`.

## 1. Climb passes (existing runs, `scripts/climb.py`)

Box x 100-120, z -118..-103 (y 19.4-21.0), times from GO at 60 vblanks/s.

| Run (config) | Lap 1 / 2 / 3 duration | HUD min, mean |
|---|---|---|
| `banc-skyaward-a0-watch` (A0) | 2.33 / 2.10 / 2.10 s | 4.07-4.10, 4.86-5.57 |
| `banc-skycont-look14` (C1+boardtimers+racecount+aimove+racetime, look 14) | 2.83 / 2.83 / 2.83 s | 3.00, 4.02-4.04 |

Profile, lap 2 (OBSERVED, `climb.py ... --every 8 --pad 0.5`): C1 HUD 7.54 at 98.13 s, 3.98 at 98.53, 3.06 at 99.07, then 3.00 from 99.47 to 100.13 s, back to 4.09 at 100.40 once past x ≈ 114. A0 lap 1: 5.54 at 31.47 s, 4.22 at 32.00, 4.07-4.25 to 32.93, 4.85 at 33.07. Distance check of the floor: C1 moves 3.82 u in 40 vblanks at HUD 3.00, so 5.7 u/s ≈ 2 x HUD (OBSERVED, from positions). The C1 lap entries come at higher speed than A0 lap 1 (A0 was recovering from a wall), so the plateau comparison is the meaningful one, not the entry.

## 2. Static reading (LEVEL_22.PRX)

- HUD setter 0x92F84 (`swc1 f12,-0x23F4(a0)` → 0x22DC0C); single caller 0x46A5C in 0x469E8, with `s0` = the player (a0 of 0x469E8; `+0x30` is the position passed to 0x92F90).
- Stores `swc1 fX,0x264(rY)` in the text (any base register, so not all are the player): 0x4424, 0xA5B4, 0x28EE0, 0x2C9FC, 0x337C0, 0x33A64, 0x34788, 0x347DC, 0x34808, 0x40BF8, 0x4DA1C, 0xE2864, 0x110A2C. Loads: 0x4430, 0xA5D8, 0x281D4, 0x28554, 0x2B9D8, 0x2FBA4, 0x2FC70, 0x33794, 0x33A38, 0x34800, 0x3482C, 0x38470, 0x46A50, 0x50C40, 0x10735C, 0x107644, 0x1077C8, 0x107BAC, 0x110B00, 0x111A40.
- Candidates by position only (INFERRED, not read): 0x2FBA4 / 0x2FC70 lie just before the substep body 0x2FE6C, and the 0x337C0-0x34808 cluster is the densest load/store group. Which of them runs per frame (2x in C1) or per substep with the delta (half in C1, as `boardtimers` showed for 0x28B34) is UNKNOWN.

## 3. Bench attempt (failed, no measurement)

- 22:45 `ppsspp_bench.py launch` (instance 1, pid 80376, port 60907 listening); `status` then timed out.
- `scripts/race.sh banc-skyboard-arrive C1+boardtimers+racecount+aimove+racetime fin-slope-c1-save --look 14 --save-at 1680 --save-name fin-slope-c1-preclimb`: `rec.py` timed out on its first debugger call (`release_all`), log `work/runs/fin-slope-c1-save.log`. No sample, no state.
- The copied `race.sh` still ran the 2026-10-23 `rec.py`, which imports the bench from `wt-banc`; it now calls `scripts/rec.py` here (paths set to `wt-slope`). At 23:27 pid 80376 was no longer running and `bench.pid` was absent (`ppsspp_bench.py quit`: "nothing to stop"); who stopped it is UNKNOWN.

## Next step (exact)

```
export RACSM_ROOT=D:/sandboxes/racsm60fps RACSM_INSTANCE=D:/sandboxes/racsm60fps/emu/ppsspp-1 RACSM_PORT=60907
python tools/bench/ppsspp_bench.py launch        # then status must answer before going on
bash research/live-tests/2026-10-24-skyboard-slope/scripts/race.sh banc-skyboard-arrive C1+boardtimers+racecount+aimove+racetime fin-slope-c1-save --look 14 --save-at 1680 --save-name fin-slope-c1-preclimb
bash research/live-tests/2026-10-24-skyboard-slope/scripts/race.sh banc-skyboard-arrive A0 fin-slope-a0-save --look 14 --save-at 1800 --save-name fin-slope-a0-preclimb
```

Then, from each preclimb state with the autopilot running (`rec.py --state fin-slope-c1-preclimb --watch <player+0x264>`): log PC / ra / value of every store to +0x264 over the climb, in C1 and A0; the slope term is the store whose decrement scales with the climb angle and is not multiplied by the delta (or is, with the substep delta). Add it as `NATIVE['LEVEL_22']['slope']` (an unrelocated instruction or a data word, README pitfall 23), then measure A0 / C1+fix / C1+fix+slope with `climb.py` and `splits.py`, `board_probe.py --script straight|turn`, and one full race (look 14).

## Questions for Linkinito (relayed by Antoine only)

1. Is player+0x264 the board speed per 1/60 s in his reading, and does his LEVEL_22 patch touch the board's slope / gravity term or a minimum-speed clamp of 0.1?

## Files

- `scripts/climb.py` (new): climb-box passes and HUD profile from `samples.json`.
- `scripts/dis.py`, `refs.py`, `aiwriter.py`, `rec.py`, `race.sh`, `splits.py`, `seg.py`: copies of the 2026-10-23/24 scripts with the bench path set to `wt-slope`.
- Raw: `work/runs/fin-slope-c1-save/` (args only) and `fin-slope-c1-save.log` (timeout), not committed.
