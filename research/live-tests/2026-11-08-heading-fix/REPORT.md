---
kind: live
title: "Sideways-walk heading overshoot under C1: caused by the camera filters, fixed by camfilters (Pokitaru, Ryllus)"
date: 2026-11-08
authors: ["Claude (Opus 5.5)"]
status: done
evidence: [OBSERVED, INFERRED]
systems: [camera, player, movement, tooling]
levels: [Pokitaru, Ryllus]
variants: [A0, C1, C1+camfilters, C1+camfilters+camera, C1+springs]
environment: "PPSSPP 1.20.4 portable, instance ppsspp-4 (port 60910), one bench instance; a second PPSSPP (ppsspp-1, another session) ran at the same time"
supersedes: [research/live-tests/2026-10-24-heading-overshoot/REPORT.md]
related: [research/live-tests/2026-10-22-coverage/REPORT.md, docs/FIX_CATALOGUE_2026-10-01.md, tools/bench/README.md]
summary: "The ~7 deg heading overshoot of C1 on a sideways walk comes from the 20 critically damped camera filters (dt = 1/30 baked in, camera updated once per frame), not from a player routine. The existing word fix camfilters brings the heading gap to A0 at 1 s from 5.7-6.9 deg down to 0.48-0.91 deg on Pokitaru and Ryllus, both directions (4/4 under 1 deg). Non-regression OK: walk 0 improves 10x (Pokitaru 0.008 -> 0.0008 u, Ryllus 0.0258 -> 0.0034 u), jump and double jump stay 0.0000, R + jump with camera 0.397 -> 0.412 u (divergence comes from the R press, same in both)."
state: "pokitaru-blaster, banc-ryllus-blaster (read only)"
---

# Heading overshoot on a sideways walk: cause and fix, 2026-11-08

Summary:

- **Cause (OBSERVED by fix, routine INFERRED):** the camera filters, not the
  player. The stick is read relative to the camera yaw. The 20 camera
  filters initialised by `0xCA24` still step with dt = 1/30 per call, and
  the camera runs once per frame, so under C1 the camera follows twice as
  fast and the walk direction turns further.
- **Fix:** the existing word fix `camfilters` (41 words: the init literal
  `0xCA2C`, the 20 computed k = omega/30 -> omega/60, the 20 e =
  exp(-omega/30) -> sqrt). No new `heading` word set was needed.
- **Result:** heading gap to A0 at 1 s, ±90 deg walk: Pokitaru 5.71 / 5.86
  deg -> 0.48 / 0.50; Ryllus 6.50 / 6.85 -> 0.76 / 0.91. 4/4 under 1 deg.
- **Residual:** it keeps growing slowly after 1 s (Ryllus 1.19 / 1.23 deg at
  1.5 s, against 7.3 / 7.4 for C1). `camera` on top changes nothing.
- **Non-regression OK:** walk 0 improves 10x on both levels, jump and
  double jump unchanged (0.0000 u), R + jump unchanged within 4 %.
- **Bench:** LEVEL_02 needed a porting rule for init-computed words
  (`level_port.py`, `levels.py`, `wordfix.py`, test `test_runtime_port.py`).

## Method

`move_probe.py --script walk --angles 90 -90` (stick held 120 vblanks), one
state per level, configs in one run so every config starts from the same
emulated state. `scripts/heading_gap.py` takes the movement heading of
`move_compare.py` (atan2 of the position step per 2 vblanks, C-configs shifted
one vblank) and reports the gap to A0 for v = 2..60 (first second).

## Heading gap to A0 (deg, sign = C-config minus A0)

| Run | Angle, config | v12 / v32 / v52 / v60 |
| --- | --- | --- |
| `hfix-pok-walk-001` | -90, C1 | 0.46 / 2.40 / 5.03 / **5.71** |
| | -90, C1+camfilters | 0.05 / -0.01 / 0.41 / **0.48** |
| | -90, C1+springs | = C1 (bit-identical) |
| | +90, C1 | -0.49 / -2.63 / -5.22 / **-5.86** |
| | +90, C1+camfilters | -0.06 / -0.01 / -0.42 / **-0.50** |
| | +90, C1+springs | = C1 (bit-identical) |
| `hfix-ryl-walk-001` | -90, C1 | 0.67 / 3.11 / 5.84 / **6.50** |
| | -90, C1+camfilters | 0.07 / -0.12 / 0.49 / **0.76** |
| | -90, C1+camfilters+camera | = C1+camfilters |
| | +90, C1 | -0.83 / -3.94 / -6.42 / **-6.85** |
| | +90, C1+camfilters | -0.09 / 0.05 / -0.70 / **-0.91** |
| | +90, C1+camfilters+camera | = C1+camfilters |

Max |gap| over v2..v60 is the v60 value in every row. C1 on instance 4
reproduces the 2026-10-22 figures of instance 1 (Pokitaru 0.46 deg at v12,
Ryllus 0.67 / 3.1 / 5.8 at v12 / 32 / 52).

After 1 s (v72 / v82 / v90): Pokitaru -90 camfilters 0.73 / 0.87 / 0.94;
Ryllus -90 1.01 / 1.13 / 1.19, +90 -1.09 / -1.17 / -1.23 (C1: 7.0 to 7.4).
Pokitaru +90 hits an obstacle near v68 in A0 and C1, so its later rows are
not a heading measure.

## Why the camera (INFERRED from the code, OBSERVED by the fix)

- The camera update `0x20F0` calls, once per frame: `0x2C84`, `0x2EB0`,
  `0x7C64`, `0x3060` (manual input), `0x804C`, `0x7740` (follow-yaw assist),
  `0x37AC`, `0x35B0`, then `0x9B80`, `0xAA44`, `0x49A0`, `0xAE14`.
- The 20 filter structs `0x2AA3E0..0x2AA5B8` are read directly only by the
  init `0xCA24` (one `lui` each, `0xCA28..0xCBD8`); the per-frame users reach
  them through the camera object.
- `camera` (manual yaw and pitch, follow-yaw assist `0x7740`) changed
  nothing on 2026-10-22 and changes nothing here on top of camfilters.
- `springs` (engine spring `0xE290`, NPC turning) changes nothing.
- Which of the 20 filters carries the yaw was not bisected (not needed for
  the fix). A bisection at one angle would name it for Linkinito.

## Bench change: init-computed words on other levels

The 20 k words are 0 in every PRX file and written at init, so the file can
neither match nor confirm their original, and `level_port.py` refused them
on LEVEL_02 ("LEVEL_01 word differs from fixes.DATA original"). Now:

- `level_port.py`: a `fixes.DATA` data word that is 0 in the LEVEL_01 file
  and nonzero in its original ports by site; the target file must hold 0 too;
  the entry carries `runtime: true`. LEVEL_02: 203 -> 223 of 327 fixes ported,
  all 41 camfilters words.
- `levels.py`: the profile lists those names in `runtime`.
- `wordfix.py`: a `runtime` word is guarded in RAM only when its fix is
  selected; unselected, a word the game has not written is skipped instead
  of refused (before, every LEVEL_02 run would check all ported words).
- `tools/bench/test_runtime_port.py`: offline, 2/2 (the 20 runtime words
  are exactly the camfilters k; LEVEL_02 ports all 41).

## Non-regression

maxDiff = max position difference to A0 over x, y, z (`move_compare.py`,
C-configs shifted one vblank). Scripts: `scripts/regress.sh`.

| Test (run) | C1 | C1+camfilters |
| --- | --- | --- |
| Pokitaru walk 0 (`hfix-pok-regress-walk0`) | 0.0080 u (10-19: 0.008) | **0.0008 u** |
| Pokitaru jump (`-jump`) | 0.0000 | 0.0000 |
| Pokitaru double jump, gaps 8/16/24/32 (`-djump`) | 0.0000 x 4 | 0.0000 x 4 |
| Pokitaru R + jump (`-rjump`) | 2.9928 u (10-20: same) | 3.0773 u |
| Pokitaru R + jump, with `camera` (`-rjump-cam`) | C1+camera 0.3972 u (10-20: same) | C1+camera+camfilters 0.4120 u |
| Ryllus walk 0 (`hfix-ryl-regress-walk0`) | 0.0258 u (10-22: same) | **0.0034 u** |
| Ryllus jump (`hfix-ryl-regress-jump`) | 0.0000 | 0.0000 |

R + jump: R is the manual camera yaw, which only `camera` restores, so the
fair pair is C1+camera against C1+camera+camfilters (`scripts/diff_time.py`):

| v | C1+camera | C1+camera+camfilters |
| --- | --- | --- |
| 40 | 0.0037 | 0.0004 |
| 60 | 0.0065 | 0.0006 |
| 80 (R pressed 56-68) | 0.088 | 0.085 |
| 120 | 0.209 | 0.214 |
| 180 | 0.394 | 0.408 |

Before R, camfilters is 10x closer to A0. Both diverge at the R press by the
same amount (residual of `camera`, known since 10-20), then camfilters ends
0.015 u (4 %) further. Verdict: no regression attributable to camfilters; the
R-yaw residual stays an open `camera` item.

## Not verified

- Camera feel. camfilters changes every camera filter (follow and
  placement), not only the yaw. The bench measures the player path only;
  the owner has to look at the camera in play.
- Levels other than Pokitaru and Ryllus.
- The residual after 1 s. Candidate, not tested: the camera history ring
  in `0xAA44` (`0x2AA5DC` = 15 frames x 1/30, listed as open in
  `docs/FIX_CATALOGUE_2026-10-01.md`).

## Answer to question 3 for Linkinito

The overshoot is known and found: it is the camera, not Ratchet's turning.
The 20 critically damped camera filters (init `0xCA24` in LEVEL_01, step
dt = 1/30 baked into k = omega x 1/30 and e = exp(-omega/30)) run once per
frame, so at 60 FPS the camera converges twice as fast, and the stick, read
relative to the camera, turns the walk further. k = omega/60 and e = sqrt(e)
restore A0 to within 1 deg over the first second on Pokitaru and Ryllus.

## Reproduce

```text
export RACSM_ROOT=D:/sandboxes/racsm60fps RACSM_INSTANCE=<root>/emu/ppsspp-4 RACSM_PORT=60910
python tools/bench/move_probe.py --state pokitaru-blaster --script walk --angles 90 -90 --configs A0 C1 C1+camfilters --out <root>/work/runs/<new>
python research/live-tests/2026-11-08-heading-fix/scripts/heading_gap.py <root>/work/runs/<new>/move.json
bash research/live-tests/2026-11-08-heading-fix/scripts/regress.sh pokitaru-blaster <prefix>
python tools/bench/test_runtime_port.py
```

The reference `LEVEL_01.PRX` (gitignored) must be copied into the worktree
first (`tools/bench/README.md`).
