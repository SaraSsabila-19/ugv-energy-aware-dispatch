#!/usr/bin/env bash
# Checks the interpreter, packages, frozen simulator identity and inputs. Changes nothing.
set -euo pipefail
source "$(dirname "$0")/config.sh"
echo "kit: $KIT"; echo "repo: $REPO"; echo "python: $PY"; echo "existing campaign (read-only): $EXISTING"; echo "output root: $OUT_ROOT"; echo "jobs: $JOBS"
"$PY" - <<PYEOF
import importlib, sys, hashlib, pathlib
print("Python", sys.version.split()[0])
missing = []
for m in ("numpy", "scipy", "networkx", "osmnx", "pandas", "fastapi", "pydantic", "httpx", "sklearn", "matplotlib"):
    try:
        mod = importlib.import_module(m); print(f"  {m:10s} {getattr(mod, '__version__', '?')}")
    except Exception as e:
        missing.append(m); print(f"  {m:10s} MISSING ({e.__class__.__name__})")
app = pathlib.Path("$REPO") / "src/frozen/app.py"
h = hashlib.sha256(app.read_bytes()).hexdigest()
print("app.py sha256", h, "OK" if h == "7b52bb550414469937da3098f91313b366137d43bd48b8465b840a97bffeb0a0" else "MISMATCH")
g = pathlib.Path("$REPO") / "inputs/utp_graph.graphml"; gx = pathlib.Path("$REPO") / "inputs/utp_graph.graphml.xml"
print("graph:", g if g.exists() else (gx if gx.exists() else "MISSING"))
print("hotspots:", (pathlib.Path("$REPO") / "inputs/hotspot_locations.csv").exists())
if missing:
    print("\nInstall missing packages with:\n  $PY -m pip install " + " ".join("scikit-learn==1.9.0" if m == "sklearn" else m for m in missing))
    sys.exit(1)
PYEOF
echo "existing campaign present: $( [ -d "$EXISTING" ] && ls "$EXISTING" | grep -c '^S4_' || echo 0 ) run folders"
