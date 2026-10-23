---
kind: live
title: "Kalidon skyboard (LEVEL_22): full race in A0 and C1, end screen, and the double-tap window (tapwin)"
date: 2026-10-23
authors: ["Claude (Opus 5.5)"]
status: partial
evidence: [OBSERVED, INFERRED]
systems: [skyboard, race-ai, input, tooling]
levels: [Kalidon Skyboard]
variants: [A0, C1, C1+tapwin]
environment: "PPSSPP 1.20.4 portable (bench instance, port 60907), JIT, plugins off; same bench as 2026-10-23-skyboard-finish"
supersedes: []
related: [research/live-tests/2026-10-23-skyboard-finish/REPORT.md, research/live-tests/2026-10-23-skyboard/REPORT.md, tools/bench/levels.py]
summary: "The autopilot finishes the 3-lap race. A0 (square held for boost) wins; the end screen shows Best Times 3:21 (race counter 6053 / 30 = 201.8 s). C1 cannot be won with the same driving: the player keeps the A0 lap pace (67 s) but the leading AI laps in 44-47 s instead of 66-74 s (about 1.5x), finishes first at 136.3 s and the screen says 'You have lost the race.'; no time is recorded on a loss, so no C1 time could be read (partial: needs a C1 AI fix first). The D-pad never reaches the double-tap detector in the race (button-enable mask 0x2000 lacks up 0x10); with that bit forced, the accepted press-to-press interval is 22-58 vblanks in A0, 10-28 in C1 and 22-58 in C1+tapwin: tapwin restores the A0 window exactly."
state: "banc-skyboard-arrive (LEVEL_22, ship arrival before the race countdown)"
---

# Kalidon skyboard, 2026-10-23 (evening): race, end screen, tapwin

Five-line summary:
1. A0 won: end screen « Best Times: Learner's Permit 3 : 21 », « Prize: Bolts: 750 » (OBSERVED, `banc-skyrace-a0-win/fin-v13587.png`, OCR); race counter 6053 calls = 201.8 s at 30 calls/s.
2. C1 lost: « You have lost the race. » (OBSERVED, `banc-skyrace-c1-ai/fin-v08505.png`, `banc-skyrace-c1-win/fin-v08266.png`). The menu then keeps « Not beaten yet »: a time is only recorded on a win, so there is no C1 time to read.
3. Why C1 loses: same player lap time as A0 (67 s), but AI 0 laps in 43.9 / 45.8 / 46.6 s in C1 against 66.9 / 69.8 s in A0, about 1.5x faster in emulated seconds (OBSERVED). Cause INFERRED: AI timestep or catch-up term not scaled for 60 fps; no C1 fix covers it yet.
4. In the race the D-pad never reaches the double-tap detector 0x1056E8: the button-enable mask read by 0x68360 is 0x2000 on every frame, without up (0x10) (OBSERVED). This is the A0 state too, so the up/down double tap is dead in this race in the original game.
5. With 0x10 forced into that mask (intervention), the window is 22-58 vblanks press-to-press in A0 (0.97 s), 10-28 in C1 (0.47 s), 22-58 in C1+tapwin: `tapwin` restores the A0 window exactly (OBSERVED, 13 gaps per config).

## Race (autopilot `rec.py`)

Driving: `research/live-tests/2026-10-23-skyboard-finish/scripts/rec.py` follows the three AI lines of one lap (`work/runs/banc-skyrace-wp/ai{0,1,2}-lap.json`, cut by `mkwp.py --lap` from the A0 AI recording `banc-skyfin-ai-a0`), switches to the line closest in height when the followed one is more than 4 u away (stacked high and low lanes), jumps at the step (152.7, -69.9) and holds square (boost) from GO. The race is 3 laps (« You have completed lap 1 / 3 », `banc-skyrace-a0-ramp3/v01500.png`).

| Run | Config | Outcome |
|---|---|---|
| `banc-skyrace-a0-full2` | A0, no boost | 3rd, « You have lost the race. », counter frozen at 6637 |
| `banc-skyrace-a0-win` | A0, boost | won, counter 6053; end screen 3:21 |
| `banc-skyrace-a0-ai` | A0, boost, AI recorded | identical to `a0-win` (GO v362, counter 6053): deterministic |
| `banc-skyrace-c1-win` | C1, boost | lost at counter 8131 (135.5 s) |
| `banc-skyrace-c1-ai` | C1, boost, AI recorded | lost at counter 8206 (136.8 s); GO v180 instead of v16, so C1 runs are not frame-identical |

The win is followed by a cutscene without text (about 1 000 vblanks without a race frame, `gap-*.png`), then the SKYBOARD CHALLENGE menu. The time shown is minutes:seconds, no hundredths; 201.8 s rounds down to 3:21. A reloaded state shows « Not beaten yet » again.

### Lap times (start-line passes, emulated seconds)

The race counter 0x240658 is +1 per frame from GO: 30/s in A0, 60/s in C1. Player passes are taken within 25 u of (-112, 66), AI passes within 8 u of each AI's own GO position (`scripts/laps.py`, `scripts/ailaps.py`; figures below copied from their output).

| Who | A0 (`a0-ai`) | C1 (`c1-ai`) |
|---|---|---|
| Player | 65.8 / 72.9 / 61.9 (wins at 201.8) | 67.4 / 67.6, race over before lap 3 |
| AI 0 | 66.9 / 69.8, lap 3 unfinished when the player wins | 43.9 / 45.8 / 46.6, finishes at 136.3 |
| AI 1 | 66.3 / 73.5 | 51.5 / 54.1 |
| AI 2 | 66.7 / 73.7 | 49.8 / 52.1 |

In A0 the win is narrow: at counter 6051 AI 1, AI 0 and AI 2 are 8.5, 20.0 and 28.8 u from their start point; at 6053 every AI position is reset onto it (end of race, not a pass). In C1 the race ends when AI 0 completes lap 3 (pass at 8181, end at 8206). In A0 the AIs pace the player: with the player idle (`banc-skyfin-ai-a0`) AI 0 laps in 93.6 s, with the player racing in 66-70 s (INFERRED: speed adapts to the player). In C1 the player is behind and AI 0 is still about 1.5x faster than in A0 (first two laps: 44.85 s against 68.35 s mean). Winning C1 as is would need a lap under about 45 s, a third faster than the A0 winning pace, so the loss is not a driving problem. The cause is INFERRED: a 1.5x ratio rather than 2x fits an unported AI timestep partly offset by a catch-up term, or a frame-based catch-up (rubber-band) term alone.

## tapwin

### Why the D-pad was never seen (`paddiag.py`)

0x1056E8 gets its pad word from 0x68260(0x10), which returns it only if 0x68360(0x10) is true: `0x10 & (mask | 1) != 0`, mask = the word loaded by the relocated `lui a1,0x0938 / lw a1,-0x2014(a1)` at base+0x68360 (0x0937DFEC in this run). Run `work/runs/banc-skyrace-paddiag-a0.json`, A0, race frames 90-246, up / down / left / right each held 20 frames: mask = 0x2000 on every frame, 0x24064C = 0 throughout. The mask has no up bit, so the detector never receives a press, whatever the debugger holds. The `pad` fields of that JSON are not the pad struct: base+0x90F08 holds MIPS code (0x27BDFFA0 = `addiu sp,sp,-0x60`), so ignore them. The game rewrites the mask every frame (forced 1 919 to 2 883 times per run below).

### Window measurement (`scripts/tapwin.py`)

Intervention: 0x10 is ORed into the mask every frame. Test: up held 6 vblanks, released GAP vblanks, held 6 again; a test starts only when the detector runs and is idle (an accepted double tap suspends it for about 400 vblanks; a refused one leaves it armed). Outcome from the detector words: accepted when 0x24064C returns to 0, refused when the second press re-arms it. Runs `work/runs/banc-skyrace-tap/{A0,C1,C1+tapwin}.json`; C1 applies 3 core writes, C1+tapwin 7 (the 4 `tapwin` words at 0x10574C, 0x105758, 0x1057B8, 0x1057C4).

| Press-to-press (vblanks) | A0 | C1 / C1+tapwin |
|---|---|---|
| 10 | refused (6 calls) | accepted (11) / refused (11) |
| 22, 26, 28 | accepted (12-15) | accepted (23-29) / accepted |
| 30, 32, 36 | accepted (16-19) | refused (31-37) / accepted |
| 52, 56, 58 | accepted (27-30) | refused (53-59) / accepted |
| 60, 62, 66 | refused (31-34) | refused (61-67) / refused |

Figure: longest accepted interval 58 vblanks (0.97 s) in A0, 28 vblanks (0.47 s) in C1, 58 vblanks (0.97 s) in C1+tapwin. Shortest accepted: 10 vblanks in C1 (0.17 s), above 10 in A0 and C1+tapwin (22 is the next tested gap). In calls the upper limit is about 30 in A0 and C1 (accepted at 29-30, refused from 31) and about 60 in C1+tapwin (59 accepted, 61 refused): tapwin doubles it so the window keeps its A0 duration. The script's dCalls looks one above the game's own difference (A0 refuses at 6 and C1+tapwin at 11, where the static bounds > 5 and > 10 would accept), so read the bounds as ±1 call. Since the mask blocks up in the original race, `tapwin` has no visible effect in normal play here (INFERRED); it matters only if another state enables 0x10.

## Commands

From the worktree root (`D:/sandboxes/racsm60fps/wt-banc`), bench PPSSPP running (`tools/bench/ppsspp_bench.py launch`):

```
export RACSM_ROOT=D:/sandboxes/racsm60fps
R=$RACSM_ROOT/work/runs; W=$R/banc-skyrace-wp
python research/live-tests/2026-10-23-skyboard-finish/scripts/rec.py --state banc-skyboard-arrive --config C1 --seconds 330 --shot-every 1200 --group 0x108CA8 --path $W/ai0-lap.json $W/ai1-lap.json $W/ai2-lap.json --lap --jump-rise 0 --jump-xz "152.7,-69.9" --boost --stuck-stop --finish-after 10 --out $R/banc-skyrace-c1-ai
python research/live-tests/2026-10-23-skyboard-race/scripts/ailaps.py $R/banc-skyrace-c1-ai/samples.json 60
python research/live-tests/2026-10-23-skyboard-finish/scripts/paddiag.py --state banc-skyboard-arrive --config A0 --out $R/banc-skyrace-paddiag-a0.json
python research/live-tests/2026-10-23-skyboard-race/scripts/tapwin.py --state banc-skyboard-arrive --config C1+tapwin --out $R/banc-skyrace-tap/C1+tapwin.json
```

Script changes this session, not committed: `rec.py` (multi-line following, finish detection and end-screen captures, gap captures), `mkwp.py` (`--lap`), `tap.py` (`--force-mask`), new `paddiag.py`, `tapwin.py`, `laps.py`, `ailaps.py`.

## Open

1. A C1 fix for the AI timestep (callback 0x108CA8 group, entities 0-2), then a C1 race to read a C1 time.
2. Whether any LEVEL_22 state sets 0x10 in the 0x0937DFEC mask (otherwise the up/down double tap is unreachable and `tapwin` can stay out of the default fix set).
