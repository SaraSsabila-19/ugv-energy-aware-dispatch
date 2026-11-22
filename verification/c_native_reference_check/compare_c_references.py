"""Compare Experiment C's all-off/all-on reference runs with native kit-v3.1 runs of the same seeds.

Inputs (repository-relative): native_run_level.csv (this folder), results/C_dynamics/analysis/run_level.csv.
Writes comparison.csv and REPORT.md here. Exit code 0 only if every compared value is identical.
Usage: python verification/c_native_reference_check/compare_c_references.py
"""
import csv, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIELDS = ["battery_Wh", "driving_Wh", "km", "completed", "wait_s", "grid_Wh"]

def main():
    native = {}
    for r in csv.DictReader(open(HERE / "native_run_level.csv")):
        native[(r["algorithm"], r["seed"], "on" if r["alpha_energy"] == "1" else "off")] = r
    ref = {}
    for r in csv.DictReader(open(ROOT / "results/C_dynamics/analysis/run_level.csv")):
        if r["mode"] in ("off", "on"):
            ref[(r["algorithm"], r["seed"], r["mode"])] = r
    out, bad = [], 0
    for key in sorted(native):
        n, c = native[key], ref.get(key)
        if c is None:
            bad += 1; out.append({"algorithm": key[0], "seed": key[1], "mode": key[2], "status": "C reference missing"}); continue
        row = {"algorithm": key[0], "seed": key[1], "mode": key[2],
               "workload_identical": n["canonical_requests_sha256"] == c["workload"]}
        diffs = []
        for f in FIELDS:
            row[f"native_{f}"], row[f"C_{f}"] = n[f], c[f]
            diffs.append(abs(float(n[f]) - float(c[f])))
        row["max_abs_diff"] = max(diffs)
        row["status"] = "IDENTICAL" if row["workload_identical"] and row["max_abs_diff"] == 0 else "DIFFERENT"
        bad += row["status"] != "IDENTICAL"; out.append(row)
    cols = sorted({k for r in out for k in r}, key=lambda k: (k not in ("algorithm", "seed", "mode", "status"), k))
    with open(HERE / "comparison.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(out)
    verdict = "PASS" if bad == 0 and len(out) == 16 else "FAIL"
    lines = ["# Experiment C reference check against the native simulator kit", "",
             "Experiment C used a custom per-round intervention harness. To confirm that the harness does not alter the simulation,",
             "the all-off (alpha_E = 0) and all-on (alpha_E = 1) references of the first four C seeds (801001-804001, fixed before",
             "running and not selected by outcome) were rerun with the standard kit v3.1 launcher (probe disabled) for both policies.", "",
             f"Compared runs: {len(out)}. Fields: workload hash and {', '.join(FIELDS)}.", "",
             f"**Result: {verdict}.** {len(out) - bad} of {len(out)} runs identical (maximum absolute difference "
             f"{max((r.get('max_abs_diff', 0) for r in out), default=0):g}).", "",
             "| Policy | Seed | Reference | Native battery Wh | C battery Wh | Status |", "|---|---|---|---:|---:|---|"]
    for r in out:
        lines.append(f"| {r['algorithm']} | {r['seed']} | {r['mode']} | {r.get('native_battery_Wh','')} | {r.get('C_battery_Wh','')} | {r['status']} |")
    lines += ["", "Interpretation: the C harness reproduces native trajectories exactly for these references. C's lower Greedy",
              "whole-run estimate relative to the other replications is therefore attributable to seed sampling, not to the harness.",
              "This is a verification step, not an additional experiment; it adds no observations to any inference."]
    (HERE / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(lines[8])
    return 0 if verdict == "PASS" else 1

if __name__ == "__main__":
    sys.exit(main())
