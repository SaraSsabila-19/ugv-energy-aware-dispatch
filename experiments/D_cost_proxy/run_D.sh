#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
PY=${PY:-$HOME/energy_soc_experiment_kit/kit/venv/bin/python}
REPO=${REPO:-$HOME/ugv-benchmark-public}
OUT_ROOT=${OUT_ROOT:-$HOME/ugv_v5_campaigns}
JOBS=${JOBS:-2}
case "${1:-}" in
  pilot) action=(run --pilot);;
  run) action=(run);;
  status) action=(status);;
  pilot-status) action=(status --pilot);;
  validate) action=(validate);;
  pilot-validate) action=(validate --pilot);;
  *) echo 'Usage: bash run_D.sh {pilot|run|status|pilot-status|validate|pilot-validate}' >&2; exit 2;;
esac
exec "$PY" experiment_d.py "${action[@]}" --repo "$REPO" --out-root "$OUT_ROOT" --jobs "$JOBS"
