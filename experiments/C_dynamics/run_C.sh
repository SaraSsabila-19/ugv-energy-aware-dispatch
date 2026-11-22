#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
REPO="${REPO:-$HOME/ugv-benchmark-public}"
PY="${PY:-$HOME/energy_soc_experiment_kit/kit/venv/bin/python}"
OUT_ROOT="${OUT_ROOT:-$HOME/ugv_v4_campaigns}"
JOBS="${JOBS:-2}"
if [[ ! -x "$PY" ]]; then echo "Python not found: $PY"; exit 1; fi
case "${1:-}" in
  pilot) args=(run --pilot);;
  run) args=(run);;
  status) args=(status);;
  pilot-status) args=(status --pilot);;
  validate) args=(validate);;
  pilot-validate) args=(validate --pilot);;
  *) echo 'Usage: bash run_C.sh {pilot|run|status|pilot-status|validate|pilot-validate}'; exit 2;;
esac
exec "$PY" experiment_c.py "${args[@]}" --repo "$REPO" --out-root "$OUT_ROOT" --jobs "$JOBS" --timeout "${TIMEOUT:-3600}"
