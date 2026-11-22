"""Regression checks that tie a v3 campaign to earlier, independently produced results.

  --existing DIR   compare every V12R100 / M825_P80 run in the campaign with the matching run of your kit-v1/v2
                   campaign (S4_<alg>_seed<seed>_soc<100|25>_a<0|1>): run_summary, energy feasibility, request results,
                   wait diagnostics, pool energy, vehicle results and the workload hash must be identical (timing columns ignored)
  --reference CSV  compare deterministic columns of run_level.csv with reference values produced by the kit author's machine
usage: python bin/regress.py --campaign OUT [--existing DIR] [--reference tests/reference_smoke_values.csv]
"""
import argparse, csv, glob, json, os
from pathlib import Path
from .common import load_json

TIMING = {"run_id", "assignment_runtime_ms", "dispatch_runtime_mean_ms", "dispatch_runtime_p95_ms", "dispatch_runtime_p99_ms",
          "dispatch_runtime_max_ms", "dispatch_budget_miss_count", "dispatch_budget_miss_percent", "trial_index"}
FILES = ["run_summary.csv", "energy_feasibility_summary.csv", "request_wait_diagnostics.csv", "request_results.csv",
         "pool_energy_summary.csv", "vehicle_results.csv"]
DET = ["completed", "battery_Wh", "km", "wait_s", "blocked_pairs", "canonical_requests_sha256", "initial_fleet_sha256",
       "r_cross", "insertion_change_pct", "matching_change_pct", "plan_E_active_Wh", "plan_E_alt_Wh"]

def same(x, y):
    """Hashes and integers must match exactly; floats within a relative 1e-9."""
    if x == y:
        return True
    try:
        fx, fy = float(x), float(y)
    except (TypeError, ValueError):
        return False
    return abs(fx - fy) <= 1e-9 * max(1.0, abs(fx), abs(fy))

def rows(p):
    return [{k: v for k, v in r.items() if k not in TIMING} for r in csv.DictReader(open(p))]

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--campaign", required=True); ap.add_argument("--existing"); ap.add_argument("--reference")
    a = ap.parse_args(argv); camp = Path(a.campaign).expanduser().resolve(); bad = 0; n = 0
    if a.existing:
        for rd in sorted((camp / "runs").glob("*")):
            if not (rd / "RUN_OK.json").exists(): continue
            sp = load_json(rd / "run_spec.json")
            if sp["fleet_config"] != "V12R100" or sp["overrides"]: continue
            lab = f"S4_{sp['algorithm']}_seed{sp['seed']}_soc{int(round(sp['initial_soc']*100))}_a{int(sp['alpha_energy'])}"
            old = glob.glob(os.path.join(os.path.expanduser(a.existing), lab, "results", "*"))
            if not old: continue
            new = rd / load_json(rd / "RUN_OK.json")["results_dir"]; n += 1
            diff = [f for f in FILES if rows(new / f) != rows(Path(old[0]) / f)]
            same_wl = (new / "canonical_requests.sha256").read_text().split()[0] == (Path(old[0]) / "canonical_requests.sha256").read_text().split()[0]
            if diff or not same_wl:
                bad += 1; print("DIFFERS", rd.name, diff, "workload ok" if same_wl else "WORKLOAD DIFFERS")
            else:
                print("identical", rd.name, "==", lab)
        print(f"existing-campaign regression: {n} runs compared, {bad} differ")
    if a.reference:
        ref = {r["label"]: r for r in csv.DictReader(open(a.reference))}
        cur = {r["label"]: r for r in csv.DictReader(open(camp / "run_level.csv"))}
        m = 0
        for lab, r in ref.items():
            if lab not in cur: continue
            m += 1
            d = [c for c in DET if c in r and not same(r[c], cur[lab].get(c))]
            if d:
                bad += 1; print("DIFFERS from reference", lab, d)
        print(f"reference regression: {m} runs compared, total differing so far {bad}")
        if m == 0:
            print("no overlapping labels with the reference file"); bad += 1
    if not a.existing and not a.reference:
        raise SystemExit("give --existing and/or --reference")
    return 1 if bad else 0
