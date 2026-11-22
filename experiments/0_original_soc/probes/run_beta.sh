#!/bin/bash
# Run ONE condition of the energy-weight x initial-SOC experiment with the frozen FIX-19 app.py.
# The frozen source is copied unchanged; extra seeds are appended in memory by wrap_run.py,
# so every archived backend_source.py keeps SHA-256 7b52bb55...0a0.
# usage: run_one.sh REPO_ROOT OUT_ROOT LABEL ALGO TRIAL_INDEX SOC ALPHA EXTRA_SEEDS_CSV
set -u
REPO=$1; OUT=$2; LABEL=$3; A=$4; T=$5; SOC=$6; AL=$7; EX=$8
KIT=$(cd "$(dirname "$0")" && pwd)
WD="$OUT/$LABEL"
if [ -f "$WD/DONE" ]; then echo "$LABEL skip"; exit 0; fi
rm -rf "$WD"; mkdir -p "$WD"
cp "$REPO/src/frozen/app.py" "$REPO/inputs/hotspot_locations.csv" "$WD/"
# The committed graph is inputs/utp_graph.graphml (some copies arrive renamed .graphml.xml)
if [ -f "$REPO/inputs/utp_graph.graphml" ]; then cp "$REPO/inputs/utp_graph.graphml" "$WD/"; else cp "$REPO/inputs/utp_graph.graphml.xml" "$WD/utp_graph.graphml"; fi
cd "$WD"
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 V2_DEPOT_LAYOUT=three V2_THREE_DEPOT_IDS=P02,P08,P16 \
"${PY:-python3}" "$KIT/wrap_run.py" "$EX" -- --headless --scenario S4 --algorithm "$A" --trial-index "$T" \
  --max-sim-s 14400 --flush-every 200 --depot-layout three --dispatch-window-s 30 --dispatch-urgent-slack-s 60 \
  --initial-soc-range "$SOC" "$SOC" --alpha-energy "$AL" --beta-time "${BETA:-1}" --soc-cost-weight 0 --cost-mode normalized \
  --energy-reference-wh 100 --time-reference-s 600 > stdout.txt 2> stderr.txt
rc=$?
[ $rc -eq 0 ] && touch DONE
echo "$LABEL exit $rc"
