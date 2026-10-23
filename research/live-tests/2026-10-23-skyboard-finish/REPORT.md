---
kind: live
title: "Kalidon skyboard (LEVEL_22): what the three C1 writers are, and the first fix measurements"
date: 2026-10-23
authors: ["Claude (Opus 5.5)"]
status: partial
evidence: [OBSERVED, INFERRED, UNKNOWN]
systems: [skyboard, race-timers, input, tooling]
levels: [Kalidon Skyboard]
variants: [A0, C1, C1+racecount, C1+boardtimers, C1+substepdt, C1+tapwin]
environment: "PPSSPP 1.20.4 portable (instance ppsspp-1, port 60907), JIT, plugins off; same bench as 2026-10-23-skyboard"
supersedes: []
related: [research/live-tests/2026-10-23-skyboard/REPORT.md, tools/bench/README.md]
summary: "The three LEVEL_22 writers that run twice as fast in C1 are a D-pad double-tap counter (0x1057F4), a race countdown set from a x30.0 conversion (0x95988) and five player timers decremented per substep (0x28B58). boardtimers (and the existing substepdt) bring the player timer back to the A0 rate with board motion unchanged; racecount restores the countdown word's duration but not the time of GO; the tapwin test is inconclusive because the bench's D-pad up never reached the game. The race was not finished: the autopilot follows the AI line and jumps the first step, then hits a pillar."
state: "banc-skyboard-arrive (LEVEL_22, ship arrival before the race countdown)"
---

# Kalidon skyboard, 2026-10-23 (afternoon): writers and fixes

Five-line summary:
1. 0x240658 is not a race clock: it is the call counter of a D-pad up/down double-tap detector (static reading).
2. `boardtimers` (one delay-slot word) and `substepdt` both make the player timer +0xA08 fall 2.0/s in C1, as in A0; board path and speed unchanged over 5 s (OBSERVED).
3. `racecount` sets the countdown word to 270/360 instead of 135/180, so it lasts the A0 time in seconds, but GO still comes 2.50 s after the countdown starts in C1 (4.97 s in A0): GO is driven by another timer (OBSERVED).
4. `tapwin` is untested in effect: the bench's `up` press never changed the detector's state in any config (OBSERVED), so the window could not be measured.
5. The end-of-race time screen was not reached (autopilot blocked by a pillar about 80 s in).

## Writers (static reading of LEVEL_22.PRX, capstone)

| Writer | Function and meaning | Candidate fix |
|---|---|---|
| 0x1057F4 (0x240658) | `0x1056E8`, once per frame from GO: counter +1 per call. Pad word from `0x68260` (reads 0x90F38). D-pad up (0x10) or down (0x40): a second press counts if the gap since the last frame the button was seen is > 5 and < 30 calls (`addiu a2,a0,-5` at 0x10574C / 0x1057B8, `addiu a2,a0,-0x1E` at 0x105758 / 0x1057C4), then calls 0x1058A0 (up) or 0x1056A8 (down) and clears 0x240648 / 0x24064C. In C1 the window is half as long in seconds. | `tapwin`: -5 -> -10, -30 -> -60 (4 words) |
| 0x95988 (0x22DDCC) | Countdown -1 per frame; set at 0x955B0 to trunc(x / 60 x 30.0), `lui a0,0x41F0` at 0x95598 (the frames30 family). | `racecount`: `lui a0,0x4270` (x 60.0) |
| 0x28B58 (player +0xA08) | `0x28B34`: player +0xA00 / A08 / A0C / A14 / A18 -= f12; called at 0x30018 in the substep body 0x2FE6C, delay slot 0x3001C `mov.s f12,f20` (substep delta: 2 x 1/30 per frame in A0, 1 x 1/60 in C1). | `boardtimers`: `add.s f12,f20,f20` (this call only); `substepdt` (ported, 0x26780) doubles the delta of the whole body |

The three candidates are in `tools/bench/levels.py` (`NATIVE['LEVEL_22']`); each word is checked against the PRX when the profile is built, and `wordfix.py` accepts the group names (`C1+tapwin`).

## Fix measurements (board_probe straight, times from GO)

Run `work/runs/banc-skyfin-fix-straight-002` (one pass per config, deterministic from the same state).

| Config | timer29E588 0.5 -> 4.9 s | countdown set to / GO after |
|---|---|---|
| A0 | 11.00 -> 2.21 (-2.00/s) | 135 / 4.97 s |
| C1 | 20.48 -> 16.09 (-1.00/s) | 135 / 2.50 s |
| C1+boardtimers | 16.97 -> 8.18 (-2.00/s) | 135 / 2.50 s |
| C1+substepdt | 16.97 -> 8.18 (-2.00/s) | 135 / 2.50 s |
| C1+racecount | 20.48 -> 16.09 (-1.00/s) | 270 / 2.50 s |

- Path, speed and HUD speed are identical to four decimals in the four C1 configs (e.g. path 99.77 at 4.9 s): neither timer fix changes board motion over 5 s.
- `boardtimers` and `substepdt` give the same timer values sample for sample. `substepdt` also touches everything else in 0x2FE6C, so `boardtimers` is the narrower fix; the rest of the body was not compared beyond these 5 s.
- `racecount`: the countdown word reaches 0 about 2.2 s after GO and restarts at 360 (A0: 180 at 30/s, the same 6 s). The C1 pre-race phase (135 at 60/s) ends before GO in both, so 0x22DDCC does not trigger GO. What starts the board is not identified (UNKNOWN).
- Not in scope but measured: `clock227D04` rises +2.0/s in C1 against +1.0/s in A0 in every C1 config; none of the three fixes touches it.

## Double tap (tap.py)

Run `work/runs/banc-skyfin-tap/{A0,C1,C1+tapwin}.json`: up held 6 vblanks, released 8 / 20 / 40 / 56 / 64 vblanks, held 6 again, state read 12 vblanks later.

- The counter 0x240658 rose 394 in 788 vblanks in A0 and 788 in C1 (30/s and 60/s, OBSERVED).
- 0x240648 and 0x24064C stayed 0 on every frame of every config: the `up` press of `ppsspp_bench.buttons` never reached the detector's pad word, so the "accepted" lines of the log are not acceptances. Either 0x68260 reads a pad word that the debugger's D-pad input does not set during the race, or the detector ignores the D-pad in this state (UNKNOWN). The effect of `tapwin` is therefore not measured.
- Next check: read 0x90F38 while holding each D-pad direction through the debugger, then repeat the test with the bit that appears.

## Race (autopilot, not finished)

- `banc-skyfin-ai-a0` (260 s, no input): the three AIs (callback 0x108CA8, entities 0-2) lap about every 2,760 race frames (92 s); the player, without input, hits a wall and respawns in a loop. Whether the race has three laps or ends with the player is not known.
- `rec.py --path` (waypoints from AI 0, 3 u apart; look-ahead 12 u; stick = -heading error / 25): the player follows the line (heading error within about 10 degrees) to (151, 22, -53), where a raised step stops it; with an automatic jump where the AI line rises more than 0.4 u within 8 u, it clears that step and hits a pillar about 80 s in (`banc-skyfin-drive-test2/v04800.png`).
- That run then stalled for 75 minutes with the CPU stopped at a break and no `cpu.stepping` event: `BreakLoop.run` now handles a stopped CPU found by its 1 s status check as a break (tools/bench/breakloop.py).

## Files

- tools/bench/levels.py: `NATIVE` candidates, checked per word against the PRX.
- tools/bench/wordfix.py: native group names, resolved in `apply()` (command line included).
- tools/bench/breakloop.py: stopped-without-event handling.
- Scripts used here (not part of the bench): `scripts/rec.py` (recorder + autopilot), `scripts/tap.py` (double-tap test), `scripts/mkwp.py` (waypoints).
- Runs (not committed): `work/runs/banc-skyfin-ai-a0`, `banc-skyfin-drive-test`, `banc-skyfin-drive-test2`, `banc-skyfin-fix-straight-002`, `banc-skyfin-tap`.

## Open

1. Finish the race (A0 then C1) for the time screen: avoid pillars (look-ahead, speed-dependent jumps or the AI's own lateral offsets).
2. Find what starts GO (the timer that ends the 2.50 s / 4.97 s phase).
3. Make the D-pad reach 0x1056E8, then measure `tapwin`.
4. `clock227D04` at twice the rate in C1.
