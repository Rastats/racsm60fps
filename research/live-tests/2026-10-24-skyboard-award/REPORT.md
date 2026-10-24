---
kind: live
title: "Kalidon skyboard (LEVEL_22): continuous C1+fix race win, the race-end award gate, and where the autopilot loses time"
date: 2026-10-24
authors: ["Claude (Opus 5.5)"]
status: done
evidence: [OBSERVED, INFERRED]
systems: [skyboard, race-awards, race-timers, tooling]
levels: [Kalidon Skyboard]
variants: [A0, C1+boardtimers+racecount+aimove+racetime]
environment: "PPSSPP 1.20.4 portable (bench instance, port 60907), JIT, plugins off; same bench as 2026-10-24-skyboard-ai"
supersedes: []
related: [research/live-tests/2026-10-24-skyboard-ai/REPORT.md, research/live-tests/2026-10-23-skyboard-race/REPORT.md, tools/bench/levels.py]
summary: "C1+boardtimers+racecount+aimove+racetime wins Learner's Permit in a continuous race (look-ahead 14: two wins, 12546 and 12003 race frames). The time award 0x79 is armed only for challenge 0x1BE, never in Learner's Permit; with the status byte forced as a test aid, the 12300 compare of racetime grants it in C1 (12003 frames) as 6150 does in A0, and refuses it when the threshold is below the time."
state: "banc-skyboard-arrive (LEVEL_22, before the countdown)"
---

# Kalidon skyboard, 2026-10-24 evening: continuous win and award gate

1. **Continuous win in C1+fix: done.** With look-ahead 14 the autopilot wins Learner's Permit from `banc-skyboard-arrive` with the full fix set (OBSERVED, twice: 12546 and 12003 race frames, records shown 3:29 and 3:20).
2. **Award gate:** award 0x79 (bit 4 of save 0x880+0x79) needs status byte +0xC armed, and the race init arms it only for challenge 0x1BE (level word 6 or 0x17, challenge index 3). In Learner's Permit (level word 0x16) it is never armed, in A0 as in C1 (OBSERVED: +0xC = 0 after every unaided race). The earlier "award for finishing under 3:25" in this race was a misreading (INFERRED in the 2026-10-24-skyboard-ai report, line 112).
3. **The compare itself works in C1** with racetime's 12300: +0xC forced to 1 (test aid) → C1 win at 12003 → +0xC = 0x40 and the save bit set; same in A0 at 6150 (6054 frames); with the threshold forced to 6000 (below the A0 time), the same A0 win gives +0xC = 0x80 and no award. A lost race leaves +0xC untouched (the gate runs only on a win).
4. **Where the autopilot loses time in C1:** two walls on segments 5-6 of each lap (hit on laps 2-3 only in C1) and the climb at (105-115, 20, -113..-108), where the C1 HUD speed floors at 3.00 against 4.1-4.5 in A0.
5. **Bench caveat:** the two C1 look-14 runs (GO detected at v68 and v293) diverge from race vblank 3, while A0 runs with GO at v110 and v362 stay identical through the finish; the cause is open.

## 1. Continuous C1+fix race

Config `C1+boardtimers+racecount+aimove+racetime` (20 words applied), from `banc-skyboard-arrive`, the `rec.py` autopilot along the three AI lines, boost, `--jump-xz "152.7,-69.9"` (`scripts/race.sh`).

| Run | Look-ahead, aid | Outcome |
|---|---|---|
| `banc-skyai-c1full` (previous report) | 12, none, no racetime | lost, 2nd; end 11919; 1 respawn |
| `banc-skyaward-c1-look12-gate` | 12, +0xC := 1 | lost, 2nd; end 11919; 1 respawn; frame-identical to `c1full` (same GO v181) |
| `banc-skycont-look14` | 14, none | **won**; end 12546; 3 respawns; record 0 → 6272 (= 12544 / 2), screen "3 : 29" (`fin-v14252.png`) |
| `banc-skyaward-c1-look14-gate` | 14, +0xC := 1 | **won**; end 12003; 1 respawn; record 6000, screen "3 : 20" (`fin-v16930.png`) |

"end" is raceFrames (0x240658) once frozen. The record stored by racetime is the race counter halved, so it stays in A0 frames (6272 / 30 = 209.1 s, shown 3:29), as designed in the previous report.

The two look-14 runs differ: GO was detected at vblank 68 in one and 293 in the other, and the player positions differ by 0.06 u from race vblank 3 on (`scripts/diverge.py`). The test aid is not the cause: it was written about 25 s after launch, long after race vblank 3 (OBSERVED). C1 runs with the same GO vblank are identical (`c1full` vs `c1-look12-gate`, GO v181: no divergence over 12820 samples). In A0 the GO vblank does not matter: `a0-watch` (GO v110), `a0-gate` and `a0-gate-thr6000` (GO v362) are identical up to race vblank 13197, after the finish, where the finish detection differs by one frame (6053 vs 6054). So C1 depends on some phase that the GO vblank tracks and A0 does not; what it is stays open.

## 2. Where the autopilot loses time (A0 win vs C1, `splits.py`, `seg.py`, `aidist.py`)

- Two walls near (66, 17, -111) and (94, 19, -120), segments 5-6 of each 1/12-lap split: A0 and C1 hit them on lap 1; only C1 hits them on laps 2 and 3. C1 lap 3: HUD speed 11.3 → 0.4 at 157.9 s, nearest AI 12.7 u away; lap 2 at 92.0 s: 8.0 → 0.8, no AI within 10 u. So the hits are not AI collisions (OBSERVED).
- Player-side C1 difference: on the climb (105-115, 20, -113..-108) the HUD speed floors at 3.00 in C1 against 4.1-4.5 in A0 (laps 1 and 3); after descents the C1 HUD reads higher (5.0 s: 20.2 vs 18.6; 8.5 s: 14.65 vs 12.9) (OBSERVED). Hypothesis: a slope term applied per frame and not ported (INFERRED, not located).
- The wins come from the autopilot setting (look-ahead 14), not from a game-side change; why look 14 loses less on these walls is not measured.

## 3. The race-end award gate (static reading, LEVEL_22.PRX)

Code at 0x106A44-0x106B60 (finish) and 0x1065E4-0x106654 (race init). The status block address is built by `lui`/`addiu` at 0x106A5C/0x106A60 and relocated at load: 0x09409970 live, RVA 0x2CFC70 from the LEVEL_22 base (`scripts/awardgate.py` reads it from RAM).

- Race init: +0xE := 1 if the level word (base+0x23D7A8) is 0x16; +0xC := 1 only if 0xDFEF0(-1, 0xFF) returns 0x1BE. 0xDFEF0 maps level word 3/0x16 → 0x1B0 + idx and 6/0x17 → 0x1B8, 0x1BA, 0x1BC, 0x1BE for idx 0-3, with idx = (save 0x880+0x4B & 0xF) % 6 (0xDFB0C). So 0x1BE = level word 6 or 0x17, challenge index 3.
- Finish, only when player race object +0xAF and +0xB0 are both nonzero: if +0xE is in 1..0x3F → award 0x78 through 0x1CE34 (bit 2 of save 0x880+0x78), +0xE := 0x40, time check skipped; else if +0xC is in 1..0x3F → race counter +0x9C <= float at base+0x24061C (6150.0 in A0; 12300.0 with racetime) ? award 0x79 (bit 4 of save 0x880+0x79) and +0xC := 0x40 : +0xC := 0x80.
- Live, unaided: +0xE goes 0 (arrive) → 1 (`a0-preramp`) → 0x80 within ~30 s of launch (load and countdown included), in A0 and in C1, by a writer not found among the block's static references (`scripts/blockrefs.py`). +0xC stays 0. After the A0 win `banc-skyaward-a0-watch` (6053 frames, 2 respawns): +0xE = 0x80, +0xC = 0, award bytes 0x78 and 0x79 both 0 (OBSERVED). So no award is given in Learner's Permit, in A0 or C1.

## 4. The 12300 compare, tested with a test aid

TEST AID, declared: about 25 s after launch (after GO and the race init) the status word is rewritten in RAM: +0xC := 1, +0xE := 0, so the finish reaches the time branch. Snapshots every 60 s (`scripts/gaterun.py` → `work/runs/<run>.gate.log`).

| Run | Config, aid | Race outcome | Gate after the finish |
|---|---|---|---|
| `banc-skyaward-a0-gate` | A0, +0xC := 1 | won, 6054, record 6051 "3:21" | +0xC = 0x40, award 0x79 byte = 0x10 (positive) |
| `banc-skyaward-c1-look14-gate` | C1+fix look 14, +0xC := 1 | won, 12003, record 6000 "3:20" | +0xC = 0x40, award 0x79 byte = 0x10 (positive, threshold 12300) |
| `banc-skyaward-c1-look12-gate` | C1+fix look 12, +0xC := 1 | lost, 2nd, 11919 | +0xC = 1 unchanged, award 0 (gate not run on a loss) |
| `banc-skyaward-a0-gate-thr6000` | A0, +0xC := 1, threshold := 6000.0 | won, 6053, record 6051 "3:21" | +0xC = 0x80, award 0x79 byte = 0 (negative) |

Counters: the "race outcome" column is raceFrames (0x240658) frozen; the gate compares the race object's +0x9C, whose stored record is 6051 (A0) and 6000 x 2 = about 12000 (C1, racetime halves it). The lost run is OBSERVED once: +0xC stayed 1, so the gate did not run.

Reading: racetime's threshold makes a C1 win at about 12000 counter frames (200 s) earn the award, as A0 at 6051 (202 s). C1 has no negative run of its own, but the compare code is the same in both: no fix word in `levels.py` falls in 0x106A44-0x106B60 or 0x1065E4-0x106654 (racetime's words are 0x10676C-0x106784, 0x106868-0x106880 and the float 0x24061C), so the A0 negative carries over (INFERRED from the word list). Without racetime the C1 counter would be compared with 6150 and no C1 win could earn it (INFERRED from the code; the previous report's arithmetic). The aid does not test the arming of +0xC for challenge 0x1BE itself. The aid writes RAM only; each run restarts from the state, but a game autosave to the bench memory stick after a win was not checked.

## Commands (from `wt-banc`, `RACSM_ROOT=D:/sandboxes/racsm60fps`)

```
bash research/live-tests/2026-10-24-skyboard-award/scripts/race.sh banc-skyboard-arrive C1+boardtimers+racecount+aimove+racetime banc-skycont-look14 --look 14
python research/live-tests/2026-10-24-skyboard-award/scripts/awardgate.py --state banc-skyboard-arrive
python research/live-tests/2026-10-24-skyboard-award/scripts/awardgate.py --set-c 1 --set-e 0 [--set-thr 6000]   # TEST AID, during the race
python research/live-tests/2026-10-24-skyboard-award/scripts/blockrefs.py
python research/live-tests/2026-10-24-skyboard-award/scripts/splits.py <run> <run>
```

```
python research/live-tests/2026-10-24-skyboard-award/scripts/gaterun.py A0 banc-skyaward-a0-gate
python research/live-tests/2026-10-24-skyboard-award/scripts/gaterun.py C1+boardtimers+racecount+aimove+racetime banc-skyaward-c1-look14-gate --look 14
THR=6000 python research/live-tests/2026-10-24-skyboard-award/scripts/gaterun.py A0 banc-skyaward-a0-gate-thr6000
python research/live-tests/2026-10-24-skyboard-award/scripts/diverge.py banc-skycont-look14 banc-skyaward-c1-look14-gate
```

`gaterun.py` launches `race.sh`, waits 25 s, applies the aid, snapshots every 60 s and after the race; logs in `work/runs/banc-skyaward-*-gate*.gate.log`.

## Open

1. Writer of 0x80 on +0xE (award 0x78, armed in Learner's Permit, failed before ~30 s in every run). Boost use is a candidate condition (INFERRED, untested).
2. The C1 player slope term on the climb (HUD floor 3.00 vs 4.1-4.5).
3. GO trigger phase: why GO lands at different vblanks after the same state load.
4. Bit 0x10 of the mask 0x0937DFEC, clock 0x227D04, cross through pad word 0x90F38 (carried over from the previous report).
5. Arming of +0xC in challenge 0x1BE itself, unaided (needs that challenge's state).
