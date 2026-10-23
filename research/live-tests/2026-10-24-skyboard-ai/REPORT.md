---
kind: live
title: "Kalidon skyboard (LEVEL_22): why the race AIs run 1.5x fast in C1, the aimove fix, and a C1 win with its end-screen time"
date: 2026-10-24
authors: ["Claude (Opus 5.5)"]
status: done
evidence: [OBSERVED, INFERRED]
systems: [skyboard, race-ai, race-timers, tooling]
levels: [Kalidon Skyboard]
variants: [A0, C1, C1+aimove, C1+aimove+aiphys, C1+boardtimers+racecount+aimove]
environment: "PPSSPP 1.20.4 portable (bench instance, port 60907), JIT, plugins off; same bench as 2026-10-23-skyboard-race"
supersedes: []
related: [research/live-tests/2026-10-23-skyboard-race/REPORT.md, research/live-tests/2026-10-23-skyboard-finish/REPORT.md, tools/bench/levels.py]
summary: "The race AI move function 0x10B4D0 keeps the velocity in units per frame and adds all of it to the position once per frame: the speed cap is 0.5367 u/frame in A0 and in C1 alike, so C1 AIs cover twice the distance per second. aimove (2 words) makes the sweep add v/2 per frame. With it the AI laps are 64.2-69.4 s in the race (A0 66.3-73.7) and, with the player idle, AI 0 laps 92.4 / 103.6 s against 93.0 / 103.8 in A0. The full C1 race is deterministic from GO and still lost by 7-54 frames with the bench autopilot; from a state saved before the last lap the player wins (look-ahead 12 and 14). End screen: Best Times Learner's Permit 6 : 59 for a real 210 s (12598 race frames at 60/s), 7 : 08 for 12865 frames: the screen shows race frames / 30, so every C1 time reads twice too long."
state: "banc-skyboard-arrive (LEVEL_22, before the countdown); banc-skyrace-c1fix-lap2end (C1+boardtimers+racecount+aimove, race frame 7701, end of lap 2)"
---

# Kalidon skyboard, 2026-10-24: race AI speed in C1

Five-line summary:
1. Cause (OBSERVED): AI velocity is in units per frame and is added whole to the position every frame (0x10C058-0x10C140); the cap +0x2C is 0.5367 u/frame in A0 and C1 alike, so C1 doubles the AI distance per second.
2. Fix `aimove` (levels.py, 2 words at 0x10C034 / 0x10C048): the sweep adds v/2 per frame. Checked live: step 0.267 u/frame in C1+aimove against 0.537 in C1.
3. AI laps with aimove: race 64.2-69.4 s (A0 66.3-73.7); player idle, AI 0 92.4 / 103.6 s against 93.0 / 103.8 in A0 (OBSERVED). `aiphys` (rest of the per-frame physics) moves laps by 0.4 s at most.
4. C1 won (OBSERVED, `banc-skyai-lap3-look14b/fin-v09099.png`): « Best Times: Learner's Permit 6 : 59 », « Prize: Bolts: 750 ». The win comes from a state saved before lap 3 (look-ahead 14; 12 also wins, 7 : 08); the full continuous C1+fix race is lost by 7-54 frames with the default autopilot.
5. The 6:59 is twice the real race time (12598 frames = 210 s, 3:30): the saved best is a frame count shown x 1/30 (A0 6053 -> 3:21, C1 12865 -> 7:08, 12289 -> 6:49). Fix `racetime` (13 words) stores it in A0 frames: the same race then shows « 3 : 29 » (`banc-skytime-fix/fin-v09089.png`).

## Cause (static reading of LEVEL_22.PRX and write breakpoints)

Writer of the AI 0 position (callback group 0x108CA8, slot 0, entity+0x30..0x38), C1, race frames 301-304 (`work/runs/banc-skyai-writer/c1.json`, `scripts/aiwriter.py`):

| PC | What | Per frame |
|---|---|---|
| 0x10B818-0x10B828, 0xD9558-0xD9564 | position saved, transformed, restored (orientation helper 0xD94C4) | no net change |
| 0x10C134 / 0x10C13C / 0x10C140 | `pos = sweep result` in the move function 0x10B4D0 | +0.55 u (cap) |
| 0x10C15C (via 0x1092CC) | ground snap of y | small |

The move function 0x10B4D0 (s0 = entity, s1 = *(entity+0x54) config, s2 = *(entity+0x58) state):
- target speed s2+0x24 = config +0x0C, or path-node speed x 1/30 (literal `lui 0x3D08 / ori 0x8889` at 0x10B8B4: a per-second value turned into per-frame); cap s2+0x2C = s2+0x24 + s2+0x28 (catch-up) + boost terms, clamped to [0x2409B4 = 2/30, 1.0];
- velocity s2+0..8 gets, per frame: throttle `dir x s2+0x30 x cap/base` (0x10BA0C), vertical step ±0x240A00 (0.00922), lateral damping 0.02 / 0.04 (0x2409C0/C4), normal damping 0.1 (0x240AB8), then a clamp to the cap;
- the sweep 0x10C058 cuts |v| into collision steps (0x18360) and adds `v x step / |v|` until |v| is used up: the whole velocity per frame, no delta anywhere.

Probe of s2+0x24 / +0x2C / +0x30 at race frame 300-600 (`a0-speed.json`, `c1-speed.json`): +0x24 = 0.65 and +0x2C = 0.5367 in both A0 and C1; +0x30 (throttle) is still ramping in A0 (0.077-0.079) and at its 0.0889 target in C1. Same per-frame cap, twice the frames per second: twice the distance per second on the straights (OBSERVED for the cap, INFERRED for the full lap). The measured 1.5x of the previous report is the race average, where corners, collisions and the catch-up reduce the gain (INFERRED).

The catch-up term s2+0x28 (write breakpoint, `c1-rubber.json`) is recomputed every frame from scratch: base 0.367 or -0.1 at 0x10AC70 (chosen from the AI's standing relative to the player), minus an integer progress count x 0x2409F0 / 5 (0x10AD5C) and an integer difference of two progress queries x 0.0833 / 2 (0x10ADF8). It accumulates nothing per frame, so it needs no port (INFERRED from the code; the base switch follows rank, not time).

## Fixes (tools/bench/levels.py `NATIVE['LEVEL_22']`)

| Group | Words | Effect |
|---|---|---|
| `aimove` | 0x10C034 `mov.s f20,f0` -> `add.s f20,f0,f0`; 0x10C048 `swc1 f20,0x7c(sp)` -> `swc1 f0,0x7c(sp)` | the sweep divides by 2\|v\| but still walks \|v\|: v/2 per frame, the A0 distance per second |
| `aiphys` (optional) | data 0x2409D8 yaw-rate gain and clamp 0.611 -> 0.305; 0x2409B8 throttle target 0.0889 -> 0.0444; 0x2409C0/C4 0.02/0.04 -> 0.01005/0.02020; 0x240AB8 0.1 -> 0.05132; 0x240A00 0.00922 -> 0.00461 | velocity changes in A0 units per 1/30 s; each word is read only by 0x10B4D0 or 0x109228 (`scripts/refs.py`) |

Not covered by `aiphys`: the two engine springs called per frame (throttle 0xDB90 from 0x109274, yaw 0xDD28 from 0x10B7A0, k and d as literals) and the mode-0 throttle target 0x2409BC (second reader 0xF6A6C; its load 0x109240 is relocated, so the word in RAM differs from the PRX and cannot be a word fix). `scripts/refit.py` holds the 60 Hz values if they are wanted later.

Check that the fix is live (`c1aimove.json`, C1+aimove, race frames 601-603): AI 0 moves 0.267 u per frame (dx 0.055, dz 0.262), half the 0.537 cap.

## AI laps (start-line passes, emulated seconds, `ailaps.py` / `laps.py`)

| Run | Config | AI 0 / AI 1 / AI 2 laps |
|---|---|---|
| `banc-skyrace-a0-ai` (23/10) | A0, race | 66.9 / 69.8 · 66.3 / 73.5 · 66.7 / 73.7 |
| `banc-skyrace-c1-ai` (23/10) | C1, race | 43.9 / 45.8 / 46.6 · 51.5 / 54.1 · 49.8 / 52.1 |
| `banc-skyai-c1aimove` | C1+aimove, race | 65.7 / 68.9 · 64.9 / 69.4 / 64.2 · 65.7 / 68.6 |
| `banc-skyai-c1aiphys` | C1+aimove+aiphys, race | 65.7 / 68.8 · 64.8 / 69.6 / 64.0 · 65.3 / 69.0 |
| `banc-skyfin-ai-a0` (23/10) | A0, player idle | 93.0 / 103.8 · 104.2 / 123.1 · 104.2 / 118.9 |
| `banc-skyai-idle-c1aimove` | C1+aimove, player idle | 92.4 / 103.6 · 109.8 / 124.4 · 105.5 / 119.9 |

With the player idle, AI 0 is within 0.6 s of A0 per lap; AI 1 and AI 2 within 1.3 s except AI 1 lap 1 (+5.6 s).

## Race outcome

Full races from `banc-skyboard-arrive`, boost, default autopilot (look-ahead 12):

| Run | Config | Outcome |
|---|---|---|
| `banc-skyai-c1aimove`, `-2` | C1+aimove | lost, 2nd; AI 1 completes lap 3 at race frame 11911, end 11919 |
| `banc-skyai-c1full` | C1+boardtimers+racecount+aimove | identical to the line above, frame for frame |
| `banc-skyai-c1aiphys` | C1+aimove+aiphys | lost, 3rd; end 11912 |

C1 runs are frame-identical from GO (player passes 3867 / 7993 / 11865 in all four), so a rerun cannot change the result. The player is not slower overall: one respawn (lap 2, race time 107.5 s) against two in A0 (107.0 and 113.0 s, `scripts/resplap.py`). Clean laps: A0 lap 1 65.8, lap 3 61.9; C1 lap 1 64.5, lap 3 64.5. The C1 autopilot loses 2.6 s on lap 3, and the catch-up keeps the leading AI within a second of the player, so the finish is decided by the last lap (INFERRED). In A0 the win was narrow too (AI 1 8.5 u short of the line).

Last lap from `banc-skyrace-c1fix-lap2end` (saved by `rec.py --save-at 7700` in a C1+boardtimers+racecount+aimove race, race frame 7701). A state load is not frame-identical with the continuous run (README gotcha 19):

| Run | Look-ahead | Outcome |
|---|---|---|
| `banc-skyai-lap3-look10` | 10 | lost, 2nd, end frame 12897 |
| `banc-skyai-lap3-look12` | 12 (the default) | won, end frame 12865, menu « Learner's Permit 7 : 08 » (`fin-v06383.png`) |
| `banc-skyai-lap3-look14` / `look14b` | 14 | won, end frame 12598 (identical in both), menu « 6 : 59 » |

The win with the default look-ahead shows that the mid-race load itself changes the race (state-load timing, AI and player positions after the reload), not the steering parameter. Each loaded run is then deterministic (look14 and look14b agree frame for frame).

## End screen (C1 time)

`banc-skyai-lap3-look14b/fin-v06459.png` to `fin-v09099.png` (read from the image): « SKYBOARD CHALLENGE », « Best Times: », « Learner's Permit 6 : 59 », « Speeding Ticket Not beaten yet », « Prize: Bolts: 750 ».

| | A0 win (23/10) | C1+fix win |
|---|---|---|
| race frames at the finish | 6053 (30/s) | 12598 (60/s) |
| real race time | 201.8 s | 210.0 s (12598 / 60; 59.7 frames per emulated second measured over the last lap, so about 211 s) |
| shown | 3 : 21 | 6 : 59 |
| frames / 30 | 201.8 -> 3:21 | 419.9 -> 6:59 |
| clock 0x227D04 GO -> finish | 202.4 -> would show 3:22 | 420.5 -> would show 7:00 (INFERRED: GO value from `c1full`, finish value from the reloaded `look14b`) |

The shown time is the race frame count / 30 in both configs (OBSERVED for the two screens; which word the menu reads is INFERRED). In C1 every recorded race time is therefore twice too long; the 6:59 corresponds to a real 3:30.

## Race time fix `racetime` (added 2026-10-24, 01:00-01:20)

Where the time comes from (static reading, then a write watch in `banc-skytime-watch`):
- The menu string « %2d : %02d » (0x138A10) is built at 0xB2250-0xB22AC: `seconds = trunc(record+0xD4 x 1/30)` (`lui 0x3D08 / ori 0x8889` at 0xB219C), then minutes and seconds by `divu 60`. The saved best time is a frame count.
- The count is the player race object (*(entity+0x58)) +0x9C, +1 per frame at 0x10672C / 0x10673C (watched at heap 0x09B3190C: 12588 -> 12592 at the finish, one write per frame). It is not 0x240658 (that word is read only by the double-tap detector).
- At the finish two identical blocks (0x106758-0x10678C and 0x106854-0x106888) read the saved best (0xE0380), compare it with +0x9C and store +0x9C (0xE086C) if it is smaller or no best exists.
- A third reader, 0x106AE8, checks `+0x9C <= 6150.0` (data 0x24061C, read only there; 205 s at 30/s) and then calls 0x1CE34 with id 0x79: an award for finishing under 3:25. In C1 this needs 102.5 s, so it is out of reach (INFERRED from the code; not triggered in any run).

`racetime` (13 words, levels.py): in both blocks the counter is halved before the compare and the store. The 4 original instructions plus the 2 `nop` delay slots are rearranged into `lbu a1 / lw a2 / srl a2 / sltu / beqz / lw a0 / srl a0`, so the stored best stays in A0 frames: saves remain comparable with A0 records and the menu's 1/30 reads right. The award threshold becomes 12300.0. The alternative (display x 1/60 at 0xB219C, 1 word) was rejected because saved A0 times would then show halved and could never be beaten.

| Run (from `banc-skyrace-c1fix-lap2end`, look-ahead 14) | Config | Race frames | Shown |
|---|---|---|---|
| `banc-skyai-lap3-look14b` | C1+boardtimers+racecount+aimove | 12598 | 6 : 59 |
| `banc-skytime-fix` | same + racetime | 12598 | **3 : 29** (`fin-v09089.png`) |

12598 / 2 / 30 = 209.97 s -> 3:29, the real race time (OBSERVED).

Compare with an existing best (01:12-01:22). The record is the save-data word `*(rcp1+0x220A60) + 0x880 + 0x50` (Learner's Permit; +0x54/+0x58/+0x5C for the other three; written at 0xE098C), read and set by `scripts/bestrec.py`. After the first C1+racetime win it holds 6298 (counter 12597 at the compare, halved), shown 3:29 (`banc-skyrec-win1`, state `banc-skyrec-menu1`). Two more wins from `banc-skyrace-c1fix-lap2end`, the record set by a test-aid RAM write after the load (`rec.py --state -`):

| Record before | Race frames | Record after | Shown |
|---|---|---|---|
| 7000 (3:53) | 12925 | 6461 (12922 / 2) | 3 : 35 (`banc-skyrec-win-rec7000/fin-v08978.png`) |
| 6000 (3:20) | 12922 | 6000, kept | 3 : 20 (`banc-skyrec-win-rec6000/fin-v09059.png`) |

Both branches of the rearranged compare work: a slower record is replaced by the halved time, a faster one is kept (OBSERVED, RAM and screen). The records were set by a write, not by two real wins in a row: a second real race needs a full continuous race, which the autopilot still loses. Not tested: the under-3:25 award (no run under 205 s).

## Commands

From the worktree root, bench PPSSPP running:

```
export RACSM_ROOT=D:/sandboxes/racsm60fps
R=$RACSM_ROOT/work/runs; W=$R/banc-skyrace-wp; S=research/live-tests/2026-10-24-skyboard-ai/scripts
python $S/aiwriter.py --state banc-skyboard-arrive --config C1 --after 300 --frames 4 --out $R/banc-skyai-writer/c1.json
python $S/aiwriter.py --state banc-skyboard-arrive --config C1 --after 600 --frames 3 --ptr 0x58 --offs 0x24,0x28,0x2c,0x30 --out $R/banc-skyai-writer/c1-speed.json
python research/live-tests/2026-10-23-skyboard-finish/scripts/rec.py --state banc-skyboard-arrive --config C1+aimove --seconds 330 --shot-every 1200 --group 0x108CA8 --path $W/ai0-lap.json $W/ai1-lap.json $W/ai2-lap.json --lap --jump-rise 0 --jump-xz "152.7,-69.9" --boost --stuck-stop --finish-after 10 --out $R/banc-skyai-c1aimove
python research/live-tests/2026-10-23-skyboard-race/scripts/ailaps.py $R/banc-skyai-c1aimove/samples.json 60
python research/live-tests/2026-10-23-skyboard-finish/scripts/rec.py --state banc-skyboard-arrive --config C1+aimove --seconds 260 --shot-every 1800 --group 0x108CA8 --out $R/banc-skyai-idle-c1aimove
python research/live-tests/2026-10-23-skyboard-finish/scripts/rec.py --state banc-skyboard-arrive --config C1+boardtimers+racecount+aimove --seconds 330 --shot-every 1200 --group 0x108CA8 --path $W/ai0-lap.json $W/ai1-lap.json $W/ai2-lap.json --lap --jump-rise 0 --jump-xz "152.7,-69.9" --boost --save-at 7700 --save-name banc-skyrace-c1fix-lap2end --out $R/banc-skyai-c1full-save
python research/live-tests/2026-10-23-skyboard-finish/scripts/rec.py --state banc-skyrace-c1fix-lap2end --config C1+boardtimers+racecount+aimove --seconds 200 --shot-every 0 --group 0x108CA8 --path $W/ai0-lap.json $W/ai1-lap.json $W/ai2-lap.json --lap --jump-rise 0 --jump-xz "152.7,-69.9" --boost --look 14 --finish-after 60 --fin-every 120 --gap-every 3 --out $R/banc-skyai-lap3-look14b
python $S/clockend.py banc-skyrace-a0-win banc-skyai-c1full banc-skyai-lap3-look14b
python research/live-tests/2026-10-23-skyboard-finish/scripts/rec.py --state banc-skyrace-c1fix-lap2end --config C1+boardtimers+racecount+aimove+racetime --seconds 200 --shot-every 0 --group 0x108CA8 --path $W/ai0-lap.json $W/ai1-lap.json $W/ai2-lap.json --lap --jump-rise 0 --jump-xz "152.7,-69.9" --boost --look 14 --finish-after 60 --fin-every 600 --gap-every 0 --watch 0x9b3190c --out $R/banc-skytime-fix
python $S/timescan.py 12289 $R/banc-skytime-scan2.json      # on the Best Times menu: RAM words near the time
```

`rec.py --watch ADDR` (added here) logs PC, ra and value of every changing store to ADDR in the events.

Script changes this session, not committed: `tools/bench/levels.py` (`aimove`, `aiphys`); `2026-10-23-skyboard-finish/scripts/rec.py` (waits up to 10 s after a state load for the entity manager and the requested groups, which raised `Invalid address` or `KeyError`; runs without `--path` no longer fail on the empty lap index); new `scripts/` here: `aiwriter.py`, `dis.py`, `refs.py`, `refit.py`, `resplap.py`, `clockend.py`.

## Open

1. `racetime`: test the under-3:25 award (a run under 205 s, e.g. from a lap-2 state with a better line).
2. A continuous C1+fix race win without a mid-race load: the default autopilot loses 2.6 s on lap 3 against A0 (cause not studied: autopilot line, AI contact or another player-side 60 fps difference).
3. `aiphys` and the two per-frame springs: measured effect on laps under 0.4 s; keep out of the default set unless a visual check shows the AI turning too sharply in C1.
