#!/bin/bash
# usage: race.sh <state> <config> <out-name> [extra rec.py args...]
export RACSM_ROOT=D:/sandboxes/racsm60fps
cd D:/sandboxes/racsm60fps/wt-slope || exit 1
R=$RACSM_ROOT/work/runs; WP=$R/banc-skyrace-wp
state=$1; config=$2; out=$3; shift 3
python research/live-tests/2026-10-24-skyboard-slope/scripts/rec.py --state "$state" --config "$config" \
  --seconds 330 --shot-every 0 --group 0x108CA8 --path $WP/ai0-lap.json $WP/ai1-lap.json $WP/ai2-lap.json \
  --lap --jump-rise 0 --jump-xz "152.7,-69.9" --boost --finish-after 60 --fin-every 600 --gap-every 0 \
  --out $R/$out "$@" > $R/$out.log 2>&1
echo "exit $?"
tail -2 $R/$out.log
