#!/usr/bin/env bash
# Usage: bash scripts/02_run_experiment.sh A     (payload, 2,000 runs)
#        bash scripts/02_run_experiment.sh B     (fleet size, 960 runs)
#        bash scripts/02_run_experiment.sh path/to/protocol.json   (any other protocol, e.g. a test)
# Resumable: rerun the same command after an interruption; finished runs are skipped, unfinished ones are moved to
# _incomplete/ and rerun. The pipeline continues to validation and analysis only when every run has finished.
set -euo pipefail
source "$(dirname "$0")/config.sh"
case "${1:-}" in
  A) P="$KIT/protocols/experiment_A_payload.json"; OUT="$OUT_ROOT/experiment_A_payload" ;;
  B) P="$KIT/protocols/experiment_B_fleet.json";   OUT="$OUT_ROOT/experiment_B_fleet" ;;
  *.json) P="$(readlink -f "$1")"; OUT="$OUT_ROOT/$(basename "$1" .json)" ;;   # any protocol file (e.g. tests/selftest_tiny.json)
  *) echo "usage: $0 A|B|path/to/protocol.json"; exit 2 ;;
esac
"$PY" "$KIT/bin/matrix.py" --protocol "$P" --campaign "$OUT" --jobs "$JOBS"
"$PY" "$KIT/bin/launch.py" --protocol "$P" --repo "$REPO" --out "$OUT" --python "$PY" --jobs "$JOBS" --timeout "$TIMEOUT" --max-retries "$RETRIES"
"$PY" "$KIT/bin/validate.py" --protocol "$P" --campaign "$OUT"
"$PY" "$KIT/bin/extract.py" --campaign "$OUT"
"$PY" "$KIT/bin/analyze.py" --protocol "$P" --campaign "$OUT"
"$PY" "$KIT/bin/figures.py" --protocol "$P" --campaign "$OUT" || echo "figures skipped (install matplotlib: $PY -m pip install matplotlib)"
"$PY" "$KIT/bin/archive.py" --protocol "$P" --campaign "$OUT" --python "$PY"
echo "Finished. Results: $OUT/analysis/  Export: $OUT/exports/"
