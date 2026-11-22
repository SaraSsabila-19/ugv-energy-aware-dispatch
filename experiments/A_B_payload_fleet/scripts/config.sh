# Paths and settings. Every value can be overridden from the environment, e.g.
#   REPO=/data/ugv-benchmark-public JOBS=6 bash scripts/02_run_experiment.sh A
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="${REPO:-/home/sara/ugv-benchmark-public}"
PY="${PY:-/home/sara/energy_soc_experiment_kit/kit/venv/bin/python}"
EXISTING="${EXISTING:-/home/sara/energy_soc_campaign_runs}"     # read-only: your 320-run campaign
OUT_ROOT="${OUT_ROOT:-$HOME/ugv_v3_campaigns}"                    # new folder for all v3 campaigns
NCPU="$(nproc 2>/dev/null || echo 2)"
JOBS="${JOBS:-$(( NCPU > 1 ? NCPU - 1 : 1 ))}"
TIMEOUT="${TIMEOUT:-3600}"
RETRIES="${RETRIES:-1}"
if [ "$(readlink -f "$OUT_ROOT")" = "$(readlink -f "$EXISTING")" ]; then
  echo "OUT_ROOT must not be your existing campaign folder ($EXISTING)."; exit 2
fi
export KIT REPO PY EXISTING OUT_ROOT JOBS TIMEOUT RETRIES
