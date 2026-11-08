---
kind: live
title: "Heading overshoot when starting a sideways walk under C1: partial, stopped 22:49 before any measurement"
date: 2026-10-24
authors: ["Claude (Opus 5.5)"]
status: partial
evidence: [OBSERVED, UNKNOWN]
systems: [player, movement, tooling]
levels: [Pokitaru, Ryllus]
variants: [A0, C1]
environment: "PPSSPP 1.20.4 portable (instance ppsspp-4, port 60910, copied from instance 1 on 2026-10-24), host CPU at 100 % with three other bench instances running"
supersedes: []
related: [research/live-tests/2026-10-22-coverage/REPORT.md, research/live-tests/pokitaru/session-2026-10-20-bench/REPORT.md, tools/bench/README.md]
summary: "Partial, stopped 22:49 (session closed by Antoine at 23:23). No heading curve was measured: the first instance-4 launch stopped answering debugger requests, and after a clean relaunch the run failed because this worktree lacks the gitignored reference LEVEL_01.PRX. Nothing new on the heading routine; the 2026-10-22 figures (about 7 deg overshoot) stay the only evidence."
state: "pokitaru-blaster (read only)"
---

# Heading overshoot on a sideways walk (C1), 2026-10-24: partial

**Partial, stopped 22:49.** Antoine closed the Ratchet sessions at 23:23.

Five-line summary:

- No measurement was obtained. The A0 vs C1 heading curve at ±90° was not
  reproduced, the heading routine was not located, and no `heading` fix
  was added to `levels.py`.
- Two blockers ate the time slot. Both are bench setup issues, not game
  findings.
- The only evidence on the overshoot is still the 2026-10-22 coverage
  report (question 3 for Linkinito): C1 turns about 7° further than A0
  during the first second, and `camera` does not change it.
- Runs `fin-heading-pok-walk-000..002` hold no samples (see below).
- The next step is written out below. It starts by copying the reference
  PRX into the worktree.

## What happened (OBSERVED)

1. **Instance 4, first launch.** Pid 75148 started and `status` answered.
   Then `move_probe.py` (`fin-heading-pok-walk-001`) and a retry
   (`-000`) timed out on their first debugger request.
   - The state was loaded: a window capture showed Ratchet at the Pokitaru
     start.
   - A bare websocket client then connected at once, but got no reply to
     `version` or `cpu.status` within 15 s.
   - `netstat` showed two server-side `CLOSE_WAIT` sockets left by the
     killed clients.
   - The host CPU was at 100 % (`compute_limit_hook`), with three other
     PPSSPP instances benching.
   - Cause: UNKNOWN. `quit` and a relaunch (pid 76688) fixed it, and
     `status` answered before and after `states.py load`.
2. **Reference PRX missing in the worktree.** Run
   `fin-heading-pok-walk-002` (walk, angles 90 and -90, A0 and C1) stopped
   in `wordfix.apply` with this error:
   "fix at +0x65174 has no known original word: reference PRX missing".
   - The file is gitignored:
     `01-Travail-et-profil-PPSSPP/Overcompensated-Reprise-2026-09-14/development-v0.6.3-generalisation/prx-reference/LEVEL_01.PRX`.
   - `wt-heading` was cut from `claude/bench-coverage`, so it does not
     carry the file. `repo/` and `wt-banc/` both have it.
   - Copying it was refused by the session scope guard, because of a
     registry slug mismatch in this session. The work stopped there.

The run directories `work/runs/fin-heading-pok-walk-000`, `-001` and `-002`
are empty. The `.log` files of `-001` and `-002` hold the tracebacks.

## Not verified (UNKNOWN)

- Whether the ~7° overshoot reproduces on instance 4. The 2026-10-22 runs
  `banc-pokitaru-walk-004-pm90` and `banc-ryllus-walk-002/-003` used
  instance 1.
- The routine that turns the player toward the stick direction, and its
  per-call constant.
- The 2026-10-22 hypothesis (INFERRED there) that a per-call smoothing step
  runs twice as often in C1.

## Next step (exact)

1. Copy the reference PRX from
   `D:/sandboxes/racsm60fps/repo/<same path>/LEVEL_01.PRX` into the
   worktree at the same path. The file is gitignored, so it is never
   committed.
2. Run the walk test on one instance, with no other instance running:

   ```text
   python tools/bench/move_probe.py --state pokitaru-blaster --script walk --angles 90 -90 --configs A0 C1 --out <root>/work/runs/<new>
   python tools/bench/move_compare.py <run>/move.json --view heading --step 10
   ```

3. Find the facing word: dump the player struct (module+0x337940) before
   and after the first 20 vblanks of the walk. Keep the float that moves
   toward ±90° relative to the camera.
4. Put a write breakpoint on that word (`breakloop.py`) to get the writer
   PC, then read the routine statically in LEVEL_01.PRX. Look for a lerp
   factor, a turn-rate clamp or a frame-counted ramp.
5. Halve it, or scale it by delta, as a `NATIVE['LEVEL_01']['heading']`
   word fix. Port it to LEVEL_02 with `level_port.py`.
6. Measure C1+heading against A0: within 1° over the first second, on both
   levels.
7. Non-regression: walk 0°, jump, double jump, R + jump.

## Questions for Linkinito

Unchanged from 2026-10-22, question 3: the sideways-walk heading overshoot
(about 7°). Is it known, and which routine smooths the heading?
