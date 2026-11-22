#!/bin/bash
# usage: run_probe.sh OUT LABEL ALGO TRIAL SOC ALPHA ALPHA_ALT EXTRA
OUT=$1; LABEL=$2; A=$3; T=$4; SOC=$5; AL=$6; ALT=$7; EX=$8
SRC=/home/claude/repo_copy; WD=$OUT/$LABEL
[ -f "$WD/probe_stats.json" ] && { echo "$LABEL skip"; exit 0; }
rm -rf "$WD"; mkdir -p "$WD"
cp "$SRC/src/frozen/app.py" "$SRC/inputs/hotspot_locations.csv" "$SRC/inputs/utp_graph.graphml" "$WD/"
cd "$WD"
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 V2_DEPOT_LAYOUT=three V2_THREE_DEPOT_IDS=P02,P08,P16 \
nice -n 10 /home/claude/venv/bin/python /home/claude/scripts/wrap_probe.py "$EX" "$ALT" -- --headless --scenario S4 --algorithm $A --trial-index $T \
 --max-sim-s 14400 --flush-every 200 --depot-layout three --dispatch-window-s 30 --dispatch-urgent-slack-s 60 \
 --initial-soc-range $SOC $SOC --alpha-energy $AL --beta-time 1 --soc-cost-weight 0 --cost-mode normalized \
 --energy-reference-wh 100 --time-reference-s 600 > stdout.txt 2> stderr.txt
echo "$LABEL exit $?"
