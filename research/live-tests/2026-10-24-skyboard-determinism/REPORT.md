---
kind: live
title: "Kalidon skyboard (LEVEL_22): C1 non-determinism after GO — partial, stopped 22:49"
date: 2026-10-24
authors: ["Claude (Opus 5.5)"]
status: partial
evidence: [OBSERVED, INFERRED, UNKNOWN]
systems: [skyboard, race-timers, tooling]
levels: [Kalidon Skyboard]
variants: [A0, C1+boardtimers+racecount+aimove+racetime]
environment: "offline analysis of existing runs under D:/sandboxes/racsm60fps/work/runs (PPSSPP 1.20.4 bench); no new bench run in this session"
supersedes: []
related: [research/live-tests/2026-10-24-skyboard-award/REPORT.md, research/live-tests/2026-10-23-skyboard-finish/REPORT.md, tools/bench/levels.py]
summary: "Partial, stopped 22:49 (session closed by Antoine at 23:23). The two C1+fix look-14 runs already differ at GO+0 (0.0156 u; launch HUD speed 9.93 vs 9.52), not at race vblank 3. Their GO ticks differ by exactly 113.000 vblanks while the A0 pair share one GO tick: rec.py applies C1 at a wall-clock moment after the state load, so a variable number of A0 frames runs first. Leading explanation (INFERRED): a bench artifact (mixed A0→C1 prefix), not a GO-phase sensitivity of C1 gameplay. Not verified live; no fix word added."
state: "banc-skyboard-arrive (LEVEL_22, before the countdown)"
---

# Kalidon skyboard: C1 non-determinism after GO (partial, stopped 22:49)

1. **Status: partial.** Offline analysis of four existing runs only; no PPSSPP run, no `levels.py` change. Stopped at 22:49, session closed at 23:23 on Antoine's request.
2. **Divergence starts at GO+0, not race vblank 3** (OBSERVED): 0.0156 u at frame 185 (GO), HUD speed 9.929 vs 9.520 at GO+1. `diverge.py`'s 0.05 u threshold is what placed it at vblank 3.
3. **Apply moment varies, GO frame does not** (OBSERVED): GO is frame 185 in all four runs; the C1 pair's GO ticks differ by exactly 113.000 vb, the A0 pair's are identical (13199830688).
4. **Pre-GO words differ in the C1 pair only** (OBSERVED): t29E588 14.13 vs 17.93 at GO, countdown 0x22DDCC 0 vs 129 at GO; clock 0x227D04 identical (6.066662).
5. **Leading explanation (INFERRED, not proven):** `rec.py` applies C1+fix at a wall-clock moment after `states.load`, so a variable number of A0 frames runs first; dt-scaled pre-GO state (boardtimers player timers, racecount's countdown init) then depends on that number. A patch active from boot cannot toggle mid-countdown, so this would be a bench artifact.

## Runs analysed (existing, `work/runs/`)

| Run | Config | First frame seen → GO |
|---|---|---|
| `banc-skycont-look14` | C1+fix, look 14 | frame 117 (countdown 62, A0-set) → GO v68, tick 12944275548 |
| `banc-skyaward-c1-look14-gate` | C1+fix, look 14 | frame 1 → GO v293, tick 12525757448 |
| `banc-skyaward-a0-watch` | A0 | frame 130 → GO v110, tick 13199830688 |
| `banc-skyaward-a0-gate` | A0 | frame 4 → GO v362, tick 13199830688 |

`v` counts from the script's first frame callback, i.e. from the attach moment, so "GO at v68 vs v293" measures attach time, not a game phase (OBSERVED from the frame numbers: GO is frame 185 in every run).

Per-frame comparison of the C1 pair (`scripts/pregog.py`): positions identical up to frame 184 (player static during the countdown), t29E588 differs from the first common frame (117) by 3.8 (= 114 frames x (1/15 - 1/30), A0 vs C1 rate with boardtimers; INFERRED arithmetic), countdown 0x22DDCC differs (62 vs 197 at frame 117). In `look14` the countdown was set under A0 (~135 frames, reaches 0 at frame ~180); in `gate` it was set after racecount took effect (~270, still 129 at GO). Launch speed then differs (9.93 ≈ A0's 9.98 vs 9.52), and the gap persists (~0.4 at GO+5).

## Not verified

- Which word causes the launch-speed gap: countdown 0x22DDCC, the boardtimers player timers (t29E588 = writer 0x28B58), or another pre-GO word (UNKNOWN). Only 5 words are recorded per frame.
- That a frame-locked apply removes the divergence (no live run).
- Whether clean C1+fix (applied from frame 1, the `gate` run) starting at 9.52 against A0's 9.98 is a real C1 gameplay difference (slower start, not faster) or an autopilot-input effect (UNKNOWN).

## Next step (exact)

1. Copy `rec.py` to `scripts/recat.py` with `--apply-frame F`: connect and set the frame-counter memcheck **before** `states.load`, detect the load by the frame value dropping to ≤ 3, apply `wordfix` at frame F while the CPU is stopped; dump base+0x200000..0x340000 at frame 184.
2. Runs (instance 3, prefix `fin-godet-`): F=1 twice with different wall delays before the load (expect identical to the finish), F=120 once, 20 s (expect the divergence at GO+0).
3. Diff the frame-184 dumps of F=1 vs F=120; force the candidates (0x22DDCC first, then player timers) to the F=1 values in an F=120 run; the word that restores the F=1 trajectory is causal; `--watch` it for the writer.
4. If confirmed, the fix is in the bench (frame-locked apply), not a `NATIVE` word; then compare clean C1+fix vs A0 launch at equal emulated time for the harmless/harmful verdict.

## Open questions for Linkinito

1. Is the C1 core (and the cheat words) active from module load in real play, or can it be toggled mid-level? If from load, the C1-vs-C1 divergence is bench-only.
2. GO comes at frame 185 in every config (clock 0x227D04 at +1/30 per frame reaches ~6.07): in C1 the race starts ~3 s after the state instead of ~6 s, while racecount's countdown still shows 129 frames. Known open item (`clock227D04` x2); is the pre-race phase in scope for the "never faster" rule?

## Scripts

```
python research/live-tests/2026-10-24-skyboard-determinism/scripts/phase.py banc-skycont-look14 banc-skyaward-c1-look14-gate
python research/live-tests/2026-10-24-skyboard-determinism/scripts/pregog.py banc-skycont-look14 banc-skyaward-c1-look14-gate --every 20
```
