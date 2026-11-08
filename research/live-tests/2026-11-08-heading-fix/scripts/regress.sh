#!/usr/bin/env bash
# Non-regression of C1+camfilters on one instance, sequential (2026-11-08).
# Usage: regress.sh <state> <run prefix>   (RACSM_ROOT / RACSM_INSTANCE / RACSM_PORT exported)
set -u
STATE=$1; PFX=$2
BENCH="$(cd "$(dirname "$0")/../../../.." && pwd)/tools/bench"
RUNS="$RACSM_ROOT/work/runs"
CFG="A0 C1 C1+camfilters"
python "$BENCH/move_probe.py" --state "$STATE" --script walk --configs $CFG --out "$RUNS/$PFX-walk0" > "$RUNS/$PFX-walk0.log" 2>&1
python "$BENCH/move_probe.py" --state "$STATE" --script jump --configs $CFG --out "$RUNS/$PFX-jump" > "$RUNS/$PFX-jump.log" 2>&1
python "$BENCH/move_probe.py" --state "$STATE" --script doublejump --gaps 8 16 24 32 --configs $CFG --out "$RUNS/$PFX-djump" > "$RUNS/$PFX-djump.log" 2>&1
python "$BENCH/move_probe.py" --state "$STATE" --script longjump --configs $CFG --out "$RUNS/$PFX-rjump" > "$RUNS/$PFX-rjump.log" 2>&1
for t in walk0 jump djump rjump; do
  echo "== $t"
  python "$BENCH/move_compare.py" "$RUNS/$PFX-$t/move.json" 2>&1 | tail -12
done
