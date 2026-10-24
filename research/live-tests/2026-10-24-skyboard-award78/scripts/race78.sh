#!/bin/bash
# usage: race78.sh <state> <config> <out-name> <seconds> [extra rec.py args...]
# rec.py autopilot (as 2026-10-24-skyboard-award/scripts/race.sh) with a write watch on the award
# status word (block +0xC..+0xF, block 0x09409970 live = RVA 0x2CFC70): every store that changes it is
# logged with PC, ra, old and new value in samples.json "events".
# Bench instance from the environment (RACSM_INSTANCE / RACSM_PORT); BOOST=0 drops --boost.
export RACSM_ROOT=${RACSM_ROOT:-D:/sandboxes/racsm60fps}
cd D:/sandboxes/racsm60fps/wt-award || exit 1
R=$RACSM_ROOT/work/runs; WP=$R/banc-skyrace-wp
state=$1; config=$2; out=$3; secs=$4; shift 4
boost=--boost; [ "${BOOST:-1}" = 0 ] && boost=
python research/live-tests/2026-10-23-skyboard-finish/scripts/rec.py --state "$state" --config "$config" \
  --seconds "$secs" --shot-every 0 --group 0x108CA8 --path $WP/ai0-lap.json $WP/ai1-lap.json $WP/ai2-lap.json \
  --lap --jump-rise 0 --jump-xz "152.7,-69.9" $boost --finish-after 60 --fin-every 600 --gap-every 0 \
  --watch 0x0940997C --out $R/$out "$@" > $R/$out.log 2>&1
echo "exit $?"
tail -2 $R/$out.log
