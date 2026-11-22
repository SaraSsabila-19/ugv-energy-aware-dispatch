"""Export a campaign for publication or independent checking, with SHA-256 checksums. Never deletes or moves runs.

Creates OUT/exports/<protocol>_<timestamp>/ with: protocol, validation report, run_level.csv, analysis/ (tables,
figures, results.json), campaign log, per-run compact records (spec, provenance, probe statistics, RUN_OK, and the
key simulator outputs), the Python environment listing, and SHA256SUMS.txt; then zips it.
  --full      also writes a .tar.gz of the complete runs/ folder (large)
  --verify Z  re-checks every checksum inside an existing export zip
With --repair (kit v3.1), the export is written to REPAIR_DIR/exports and contains the ORIGINAL run records unchanged
(runs_compact/), the repaired probe records (repaired_runs_compact/), repair_report, the original validation report
(original_validation_report.*), and the merged validation, run_level and analysis from the repair folder.
usage: python bin/archive.py --protocol P.json --campaign OUT [--repair REPAIR_DIR] [--python PY] [--full]
       python bin/archive.py --verify path/to/export.zip
"""
import argparse, hashlib, io, json, shutil, subprocess, sys, tarfile, time, zipfile
from pathlib import Path
from .common import load_json, sha256_file, write_json

KEEP = ["run_summary.csv", "run_settings.json", "canonical_requests.sha256", "energy_feasibility_summary.csv",
        "request_results.csv", "request_wait_diagnostics.csv", "cost_diagnostics.csv", "pool_energy_summary.csv",
        "vehicle_results.csv", "dispatch_invocation_events.csv", "headless_status.json"]

def verify(zpath):
    bad = 0
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist(); root = names[0].split("/")[0]
        sums = z.read(f"{root}/SHA256SUMS.txt").decode().splitlines()
        for line in sums:
            h, rel = line.split("  ", 1)
            if hashlib.sha256(z.read(f"{root}/{rel}")).hexdigest() != h:
                print("MISMATCH", rel); bad += 1
    print(f"{len(sums)} files checked, {bad} mismatches"); return 1 if bad else 0

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--protocol"); ap.add_argument("--campaign"); ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--full", action="store_true"); ap.add_argument("--verify", default=None); ap.add_argument("--repair", default=None)
    a = ap.parse_args(argv)
    from .probe import refuse_legacy_write
    refuse_legacy_write(Path(a.campaign).expanduser().resolve(), a.repair, 'archive')
    if a.verify:
        return verify(a.verify)
    protocol = load_json(a.protocol); camp = Path(a.campaign).expanduser().resolve()
    base = Path(a.repair).expanduser().resolve() if a.repair else camp
    stamp = time.strftime("%Y%m%dT%H%M%S"); name = f"{protocol['protocol_id']}_{'repaired_' if a.repair else ''}{stamp}"
    ex = base / "exports" / name; ex.mkdir(parents=True)
    shutil.copy2(a.protocol, ex / Path(a.protocol).name)
    for f in ("validation_report.json", "validation_report.md", "run_level.csv"):
        if (base / f).exists(): shutil.copy2(base / f, ex / f)
    for f in ("campaign_log.csv", ".ugvkit_campaign.json"):
        if (camp / f).exists(): shutil.copy2(camp / f, ex / f.lstrip("."))
    if a.repair:
        for f in ("validation_report.json", "validation_report.md"):
            if (camp / f).exists(): shutil.copy2(camp / f, ex / f"original_{f}")
        for f in ("repair_report.json", "repair_report.md", "affected_runs.csv", "campaign_log.csv", ".ugvkit_repair.json", "DEVIATIONS_entry.md"):
            if (base / f).exists(): shutil.copy2(base / f, ex / ("repair_" + f.lstrip(".") if f in ("campaign_log.csv", ".ugvkit_repair.json") else f))
        for rd in sorted((base / "runs").glob("*")):
            if not (rd / "RUN_OK.json").exists(): continue
            dst = ex / "repaired_runs_compact" / rd.name; dst.mkdir(parents=True)
            for f in ("run_spec.json", "overrides_and_provenance.json", "probe_stats.json", "RUN_OK.json"):
                if (rd / f).exists(): shutil.copy2(rd / f, dst / f)
    if (base / "analysis").exists(): shutil.copytree(base / "analysis", ex / "analysis")
    n = 0
    for rd in sorted((camp / "runs").glob("*")):
        if not (rd / "RUN_OK.json").exists(): continue
        ok = load_json(rd / "RUN_OK.json"); dst = ex / "runs_compact" / rd.name; (dst / "results").mkdir(parents=True)
        for f in ("run_spec.json", "overrides_and_provenance.json", "probe_stats.json", "RUN_OK.json"):
            if (rd / f).exists(): shutil.copy2(rd / f, dst / f)
        for f in KEEP:
            src = rd / ok["results_dir"] / f
            if src.exists(): shutil.copy2(src, dst / "results" / f)
        n += 1
    try:
        frz = subprocess.run([a.python, "-m", "pip", "freeze", "--all"], capture_output=True, text=True, timeout=120).stdout
    except Exception as e:
        frz = f"pip freeze failed: {e}"
    (ex / "environment_pip_freeze.txt").write_text(frz)
    from . import __version__, FROZEN_APP_SHA256
    write_json(ex / "export_info.json", {"kit_version": __version__, "frozen_app_sha256": FROZEN_APP_SHA256, "runs_exported": n,
                                         "created": stamp, "campaign": str(camp)})
    files = sorted(p for p in ex.rglob("*") if p.is_file())
    (ex / "SHA256SUMS.txt").write_text("\n".join(f"{sha256_file(p)}  {p.relative_to(ex)}" for p in files) + "\n")
    zpath = base / "exports" / f"{name}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ex.rglob("*")):
            if p.is_file(): z.write(p, f"{name}/{p.relative_to(ex)}")
    print(f"export: {zpath} ({n} runs)"); verify(zpath)
    if a.full:
        tpath = base / "exports" / f"{name}_full_runs.tar.gz"
        with tarfile.open(tpath, "w:gz") as t:
            t.add(camp / "runs", arcname=f"{name}_runs")
        (base / "exports" / f"{name}_full_runs.tar.gz.sha256").write_text(f"{sha256_file(tpath)}  {tpath.name}\n")
        print("full archive:", tpath)
    return 0
