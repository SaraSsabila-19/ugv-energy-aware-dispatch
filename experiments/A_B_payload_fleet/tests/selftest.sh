#!/usr/bin/env bash
# Tests the kit's safety features on a throwaway folder (8 short runs, about 2-3 minutes):
#  1 refusal to write into a non-empty folder the kit did not create
#  2 failure detection: a 1-second timeout makes every run fail and writes RUN_FAILED.json
#  3 resume: a normal relaunch moves failed attempts to _incomplete/ and completes the runs
#  4 no repetition: a third launch skips every finished run
#  5 validation and extraction on the result
#  6 a second launcher on the same folder is refused; Ctrl-C/SIGTERM stops running simulations; relaunch completes them
set -euo pipefail
source "$(dirname "$0")/../scripts/config.sh"
T="$OUT_ROOT/_kit_selftest_$(date +%Y%m%dT%H%M%S)"; mkdir -p "$T/foreign"; echo x > "$T/foreign/file.txt"
P="$KIT/tests/selftest_tiny.json"
echo "1) refusal"; if "$PY" "$KIT/bin/launch.py" --protocol "$P" --repo "$REPO" --out "$T/foreign" --python "$PY" --jobs 2; then echo "FAIL: wrote into foreign folder"; exit 1; else echo "   refused as expected"; fi
echo "2) forced failures"; "$PY" "$KIT/bin/launch.py" --protocol "$P" --repo "$REPO" --out "$T/c" --python "$PY" --jobs 2 --timeout 1 --max-retries 0 && { echo "FAIL: timeouts not detected"; exit 1; } || true
n=$(ls "$T"/c/runs/*/RUN_FAILED.json | wc -l); echo "   RUN_FAILED files: $n"; [ "$n" -eq 4 ] || { echo FAIL; exit 1; }
echo "3) resume"; "$PY" "$KIT/bin/launch.py" --protocol "$P" --repo "$REPO" --out "$T/c" --python "$PY" --jobs 2
n=$(ls "$T"/c/runs/*/RUN_OK.json | wc -l); m=$(ls -d "$T"/c/_incomplete/* | wc -l); echo "   RUN_OK: $n, earlier attempts preserved in _incomplete: $m"; [ "$n" -eq 4 ] && [ "$m" -eq 4 ] || { echo FAIL; exit 1; }
echo "4) skip finished"; out=$("$PY" "$KIT/bin/launch.py" --protocol "$P" --repo "$REPO" --out "$T/c" --python "$PY" --jobs 2); echo "$out" | head -1; echo "$out" | grep -q "4 already complete, 0 to run" || { echo FAIL; exit 1; }
echo "5) validate + extract"; "$PY" "$KIT/bin/validate.py" --protocol "$P" --campaign "$T/c" >/dev/null && "$PY" "$KIT/bin/extract.py" --campaign "$T/c"
echo "6) concurrent launcher refused, Ctrl-C stops runs cleanly, resume completes"
"$PY" "$KIT/bin/launch.py" --protocol "$P" --repo "$REPO" --out "$T/i" --python "$PY" --jobs 2 > "$T/interrupt.log" 2>&1 &
LP=$!; sleep 5
if "$PY" "$KIT/bin/launch.py" --protocol "$P" --repo "$REPO" --out "$T/i" --python "$PY" --jobs 2 >/dev/null 2>&1; then echo "FAIL: second launcher was allowed"; exit 1; else echo "   second launcher refused"; fi
kill -TERM "$LP"; set +e; wait "$LP"; rc=$?; set -e; echo "   interrupted launcher exit code $rc"
[ "$rc" -eq 130 ] || { echo "FAIL: launcher did not stop on SIGTERM"; exit 1; }
grep -q "interrupted by user" "$T"/i/runs/*/RUN_FAILED.json || { echo "FAIL: interrupted runs not marked"; exit 1; }
if pgrep -f "runner.py --run-dir $T/i" >/dev/null; then echo "FAIL: orphan simulator processes"; exit 1; fi
"$PY" "$KIT/bin/launch.py" --protocol "$P" --repo "$REPO" --out "$T/i" --python "$PY" --jobs 2 >/dev/null
n=$(ls "$T"/i/runs/*/RUN_OK.json | wc -l); [ "$n" -eq 4 ] || { echo "FAIL: resume after interrupt"; exit 1; }
"$PY" "$KIT/bin/validate.py" --protocol "$P" --campaign "$T/i" >/dev/null && echo "   resumed and validated"
echo "SELFTEST PASSED ($T)"
