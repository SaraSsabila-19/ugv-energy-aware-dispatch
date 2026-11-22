#!/usr/bin/env bash
# 1) Regression: re-runs 16 conditions of your existing 320-run campaign with the v3 runner (probe ON) and requires
#    byte-identical simulator outputs (timing columns excluded).
# 2) Smoke tests: 22 runs on seed 904001 (payload levels + all three fleet configurations), full pipeline, and a
#    comparison with the reference values produced on the kit author's machine.
# About 5-10 minutes with 4 cores. Safe to rerun: finished runs are skipped.
set -euo pipefail
source "$(dirname "$0")/config.sh"
mkdir -p "$OUT_ROOT"
echo "== Regression against your existing campaign =="
"$PY" "$KIT/bin/launch.py" --protocol "$KIT/tests/regress_existing.json" --repo "$REPO" --out "$OUT_ROOT/regress_existing" --python "$PY" --jobs "$JOBS"
"$PY" "$KIT/bin/regress.py" --campaign "$OUT_ROOT/regress_existing" --existing "$EXISTING"
for P in smoke_payload smoke_fleet; do
  echo "== Smoke: $P =="
  OUT="$OUT_ROOT/$P"
  "$PY" "$KIT/bin/launch.py"   --protocol "$KIT/protocols/$P.json" --repo "$REPO" --out "$OUT" --python "$PY" --jobs "$JOBS"
  "$PY" "$KIT/bin/validate.py" --protocol "$KIT/protocols/$P.json" --campaign "$OUT"
  "$PY" "$KIT/bin/extract.py"  --campaign "$OUT"
  "$PY" "$KIT/bin/regress.py"  --campaign "$OUT" --reference "$KIT/tests/reference_smoke_values.csv"
done
echo "Smoke and regression checks passed."
