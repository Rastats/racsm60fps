---
kind: live
title: "Kalidon skyboard (LEVEL_22): race-end award 0x78, writer of 0x80 on status +0xE (partial, stopped 22:49)"
date: 2026-10-24
authors: ["Claude (Opus 5.5)"]
status: partial
evidence: [OBSERVED, INFERRED, UNKNOWN]
systems: [skyboard, race-awards, tooling]
levels: [Kalidon Skyboard]
variants: [A0]
environment: "PPSSPP 1.20.4 portable, bench instance 2 (emu/ppsspp-2, port 60908), JIT, plugins off; worktree wt-award, branch claude/l22-award78"
supersedes: []
related: [research/live-tests/2026-10-24-skyboard-award/REPORT.md, tools/bench/levels.py]
summary: "Partial, stopped 22:49 (closure asked by Antoine at 23:23). One A0 autopilot race with boost: +0xE reads 0x80 afterwards, but the rec.py write watch on block +0xC logged no store, because the watch is armed after the load, the wordfix pass and the entity wait, and the emulator kept running after the run. Writer of 0x80, its condition, its frame-rate dependence and A0 / C1+fix parity on 0x78: not established. Next: watch78.py (watch armed right after the load), idle then square held."
state: "banc-skyboard-arrive (LEVEL_22, before the countdown)"
---

# Kalidon skyboard: award 0x78 writer, partial (stopped 22:49)

1. **Status: partial.** Antoine asked at 23:23 to close the Ratchet sessions; the last bench command (22:49) was refused, no measurement since. Success predicate not met.
2. **Measured:** status block live at 0x09409970 (RVA 0x2CFC70), +0xE = 1 about 1.5 s after loading `banc-skyboard-arrive` (OBSERVED, `awardgate.py`).
3. **Measured:** run `work/runs/fin-award-a0-boost-w` (A0, autopilot with boost, 60 emulated s, `--watch 0x0940997C`): no watch event; afterwards +0xE = 0x80 (OBSERVED).
4. **Why no writer was caught:** the watch existed only during the 60 s loop, which starts after the load, the wordfix pass and up to 10 s of entity wait; the emulator kept running after the script, several minutes before the read (INFERRED). A memcheck-bypassing copy is not excluded (UNKNOWN).
5. **Next step:** run `scripts/watch78.py` (watch armed right after the load, CPU paused at the end) with no input, then with square held, to get the writer PC and test boost.

## What was done

| Step | Run / tool | Result | Label |
|---|---|---|---|
| Block address after load | `2026-10-24-skyboard-award/scripts/awardgate.py --state banc-skyboard-arrive` | block 0x9409970, bytes `00 … 00 01 00`: +0xC = 0, +0xE = 1, threshold 6150.0, challenge idx 0 | OBSERVED |
| A0 race with boost, watch on +0xC..+0xF | `scripts/race78.sh banc-skyboard-arrive A0 fin-award-a0-boost-w 60` | GO at sample v0; 1798 frames, last v3594, raceFrames 1923; events: GO and 3 line changes, **no watch event** | OBSERVED |
| Block after the run (minutes later, emulator running) | `awardgate.py` | +0xE = 0x80, +0xC = 0 | OBSERVED |
| `watch78.py` A0 idle | `fin-award-w-a0-idle` | first try: timeout in `wordfix.apply` (it pauses an already paused CPU); fixed in the script; second try refused (closure) | no data |

Between 22:41 and 22:47 the PreToolUse guard hook timed out on every tool call (about 10 in a row), so the emulator ran unobserved after the run; this is why the read after the run does not date the write.

## Not established

- Writer PC of 0x80 on +0xE and its condition (boost, count, duration, frame-counted timer): UNKNOWN. Boost stays the candidate from the previous report (INFERRED, untested).
- Frame-rate dependence of that condition under C1: UNKNOWN.
- A0 / `C1+boardtimers+racecount+aimove+racetime` parity on 0x78, granting and refusing cases: not measured. No fix word added to `levels.py`.
- Whether the 0x80 store passes through a CPU store at all (a block copy or HLE memcpy would not stop a memcheck): UNKNOWN.

## Next step, exact

From `wt-award`, instance 2 environment exported (`RACSM_ROOT=D:/sandboxes/racsm60fps RACSM_INSTANCE=…/emu/ppsspp-2 RACSM_PORT=60908`), after `ppsspp_bench.py launch`:

```
python research/live-tests/2026-10-24-skyboard-award78/scripts/watch78.py --state banc-skyboard-arrive --seconds 40 --out fin-award-w-a0-idle
python research/live-tests/2026-10-24-skyboard-award78/scripts/watch78.py --state banc-skyboard-arrive --seconds 40 --hold square --out fin-award-w-a0-square
```

- A break with `store` = `[0xe, 1, 0x80]`: disassemble around its `pc` and `ra` (`dis.py`), read the condition, then repeat with `--config C1+boardtimers+racecount+aimove+racetime`.
- No break but +0xE = 0x80 at the end (`end.bytes`): look for a copy routine writing the block (read watch on the source, or a CPU breakpoint on memcpy callers).
- +0xE still 1 after 40 s idle: the condition needs input; compare square held vs not.
- Then parity: one granting case (condition not met, finish won → award byte 0x78 bit 2) and one refusing case, A0 vs C1+fix, as in the previous report's §4.

## Scripts

- `scripts/race78.sh`: the 2026-10-24 autopilot (`rec.py`, look 12, boost unless `BOOST=0`) with `--watch 0x0940997C`; logs PC, ra, old and new of each store changing the status word.
- `scripts/watch78.py`: watch armed right after the state load, no autopilot, optional `--hold` / `--stick` / `--config`; logs tick, PC, ra, pending store, registers and 16 stack words per break; leaves the CPU paused. Not run successfully yet.

## Open questions for Linkinito

1. Does award 0x78 in Learner's Permit mean "finish without boosting" (or another "without X" rule)? Its status byte is armed at race init (+0xE := 1) and marked failed (0x80) early in every bench race.
2. Is the 0x80 write in code you have already mapped (a boost or pickup handler outside 0x106A44-0x106B60)?
