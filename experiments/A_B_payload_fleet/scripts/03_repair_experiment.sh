#!/usr/bin/env bash
# Kit v3.1 probe-accounting repair for a campaign finished with kit v3.0 (e.g. Experiment B).
# Usage: bash scripts/03_repair_experiment.sh B        (or A, or path/to/protocol.json)
#   CAMPAIGN=/path/to/original  REPAIR=/path/to/new_repair_folder   (optional overrides)
# Steps: identify affected runs -> rerun ONLY those into a separate repair folder -> verify each against its original ->
#        validate the complete campaign with the verified repaired probe records -> extract, analyze, figures, export.
# The original campaign folder is read-only throughout. Safe to rerun: finished repairs are skipped.
set -euo pipefail
source "$(dirname "$0")/config.sh"
case "${1:-}" in
  A) P="$KIT/protocols/experiment_A_payload.json"; NAME=experiment_A_payload ;;
  B) P="$KIT/protocols/experiment_B_fleet.json";   NAME=experiment_B_fleet ;;
  *.json) P="$(readlink -f "$1")"; NAME="$(basename "$1" .json)" ;;
  *) echo "usage: $0 A|B|path/to/protocol.json"; exit 2 ;;
esac
CAMPAIGN="${CAMPAIGN:-$OUT_ROOT/$NAME}"
REPAIR="${REPAIR:-$OUT_ROOT/${NAME}_probe_repair_v3.1}"
[ -d "$CAMPAIGN/runs" ] || { echo "Original campaign not found: $CAMPAIGN"; exit 2; }
echo "original campaign (read-only): $CAMPAIGN"; echo "repair folder: $REPAIR"
"$PY" "$KIT/bin/repair.py"   --protocol "$P" --campaign "$CAMPAIGN" --repair-out "$REPAIR" --repo "$REPO" --python "$PY" --jobs "$JOBS" --timeout "$TIMEOUT" --max-retries "$RETRIES"
"$PY" "$KIT/bin/validate.py" --protocol "$P" --campaign "$CAMPAIGN" --repair "$REPAIR"
"$PY" "$KIT/bin/extract.py"  --campaign "$CAMPAIGN" --repair "$REPAIR"
"$PY" "$KIT/bin/analyze.py"  --protocol "$P" --campaign "$CAMPAIGN" --repair "$REPAIR"
"$PY" "$KIT/bin/figures.py"  --protocol "$P" --campaign "$CAMPAIGN" --repair "$REPAIR" || echo "figures skipped (install matplotlib)"
"$PY" "$KIT/bin/archive.py"  --protocol "$P" --campaign "$CAMPAIGN" --repair "$REPAIR" --python "$PY"
echo "Done. Repair report: $REPAIR/repair_report.md   Validation: $REPAIR/validation_report.md   Analysis: $REPAIR/analysis/"
echo "Append $REPAIR/DEVIATIONS_entry.md to $KIT/protocols/DEVIATIONS.md (and your records)."
