#!/usr/bin/env bash
# One-time publication of this package to GitHub, run on your own machine.
#
#   bash tools/publish_to_github.sh  /path/to/folder/with/the/EXP_zips  [remote-url]
#
# 1. Copies the six campaign archives (EXP_A ... EXP_F .zip) from the folder you give (searched up to 3 levels deep)
#    into archives/, and refuses to continue unless every archive matches archives/ARCHIVES.sha256 exactly.
# 2. Runs verification/verify_repository.py (46 checks) and stops on any failure.
# 3. Creates the initial commit and pushes branch main to the remote (default: your ugv-energy-aware-dispatch repo).
# The remote repository must already exist and be EMPTY (github.com/new, no README/licence/.gitignore).
# Nothing outside this folder is modified; the source folder is only read.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="${1:?usage: bash tools/publish_to_github.sh /path/to/folder/with/EXP_zips [remote-url]}"
REMOTE="${2:-https://github.com/SaraSsabila-19/ugv-energy-aware-dispatch.git}"
if [ -z "${PY:-}" ]; then
  if [ -x "$HOME/energy_soc_experiment_kit/kit/venv/bin/python" ]; then PY="$HOME/energy_soc_experiment_kit/kit/venv/bin/python"; else PY=python3; fi
fi
"$PY" -c "import numpy, scipy" 2>/dev/null || { echo "Python at $PY needs numpy and scipy (pip install -r requirements.txt)"; exit 1; }

echo "== 1/3  Campaign archives"
for f in $(awk '{print $2}' archives/ARCHIVES.sha256 | grep -v '^provenance/'); do
  if [ ! -f "archives/$f" ]; then
    cand="$(find "$SRC" -maxdepth 3 -type f -name "$f" 2>/dev/null | head -1)"
    [ -n "$cand" ] || { echo "Not found under $SRC: $f"; exit 1; }
    cp "$cand" "archives/$f"; echo "   copied $f"
  fi
done
(cd archives && sha256sum -c ARCHIVES.sha256 --quiet) && echo "   all $(wc -l < archives/ARCHIVES.sha256) archives match their SHA-256"

echo "== 2/3  Verification"
"$PY" verification/verify_repository.py | tail -3
"$PY" verification/verify_repository.py > /dev/null || { echo "Verification failed: nothing was committed or pushed."; exit 1; }

echo "== 3/3  Commit and push to $REMOTE"
[ -d .git ] || git init -q -b main
git config user.name >/dev/null || git config user.name "Saraban Salsabila"
git config user.email >/dev/null || git config user.email "314928998+SaraSsabila-19@users.noreply.github.com"
git add -A
if git rev-parse --verify HEAD >/dev/null 2>&1 && git diff --cached --quiet; then
  echo "   nothing new to commit"
else
  git commit -q -F - <<'MSG'
Reproducibility package v1.0.0: energy-aware online dispatch study

Frozen simulator, byte-identical experiment kits for the original 2x2 and
Experiments A-F, prespecified protocols, complete campaign archives
(14,013 validated runs), result tables, post hoc replication synthesis,
and verification scripts that recompute every reported contrast.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_012Rzb1XAhZaDXwNdkGM71NT
MSG
  echo "   committed $(git ls-files | wc -l) files"
fi
git remote get-url origin >/dev/null 2>&1 && git remote set-url origin "$REMOTE" || git remote add origin "$REMOTE"
git push -u origin main
echo
echo "Published: ${REMOTE%.git}"
echo "Next: check the 'verify' workflow under the repository's Actions tab, then see docs/DATA_AVAILABILITY.md for the release and DOI."
