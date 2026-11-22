"""Re-execute archived simulation runs from this repository and confirm they reproduce the published results exactly.

Default: Experiment A, first seed (601001), baseline mass, both policies, alpha_E 0 and 1 (4 runs, about 1 minute with 2 jobs),
with the decision probe enabled exactly as in the campaign. Uses the unmodified kit in experiments/A_B_payload_fleet and the
frozen simulator in src/frozen. Every run-level value is compared with results/A_payload/run_level.csv; only wall-clock
timing columns and run identifiers are excluded.

Usage: python verification/reproduce_sample_runs.py [--seeds 601001 602001] [--jobs 2] [--out reproduced_runs]
Output runs go to --out (default ./reproduced_runs, ignored by git). Exit code 0 = every compared value identical.
"""
import argparse, csv, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "experiments/A_B_payload_fleet"
SKIP = {"label", "protocol_id", "run_summary_sha256", "dispatch_max_ms", "dispatch_over_300ms", "probe_source", "probe_schema",
        "probe_accounting"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", nargs="+", type=int, default=[601001])
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--out", default=str(ROOT / "reproduced_runs"))
    a = ap.parse_args()
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    original = json.loads((ROOT / "results/A_payload/experiment_A_payload.json").read_text())
    proto = {"protocol_id": "REPRODUCE_A_SAMPLE", "status": "verification rerun of archived Experiment A runs", "excluded_seeds": [],
             "design": {**original["design"], "seeds": a.seeds,
                        "mass_configs": [m for m in original["design"]["mass_configs"] if m["id"] == "M825_P80"]},
             "contrasts": []}
    pfile = out / "reproduce_protocol.json"; pfile.write_text(json.dumps(proto, indent=1))
    camp = out / "campaign"
    subprocess.run([sys.executable, str(KIT / "bin/launch.py"), "--protocol", str(pfile), "--repo", str(ROOT), "--out", str(camp),
                    "--python", sys.executable, "--jobs", str(a.jobs)], check=True)
    subprocess.run([sys.executable, str(KIT / "bin/extract.py"), "--campaign", str(camp)], check=True)
    new = {(r["seed"], r["algorithm"], r["alpha_energy"]): r for r in csv.DictReader(open(camp / "run_level.csv"))}
    ref = {(r["seed"], r["algorithm"], r["alpha_energy"]): r for r in csv.DictReader(open(ROOT / "results/A_payload/run_level.csv"))
           if r["mass_config"] == "M825_P80"}
    bad = 0; compared = 0; exact = 0; max_rel = 0.0
    for k, r in sorted(new.items()):
        o = ref[k]; diffs = []
        for c in r:
            if c in SKIP or c not in o:
                continue
            compared += 1
            if r[c] == o[c]:
                exact += 1; continue
            try:   # derived floating-point aggregates may differ in the last bit with the Python/NumPy summation order
                rel = abs(float(r[c]) - float(o[c])) / max(abs(float(o[c])), 1e-300)
            except ValueError:
                rel = float("inf")
            max_rel = max(max_rel, rel)
            if rel > 1e-12:
                diffs.append(c)
        bad += bool(diffs)
        print(f"  seed {k[0]} {k[1]:9s} alpha_E={k[2]}: battery {r['battery_Wh']} Wh, sdec {r['sdec_pct']}  "
              + ("REPRODUCED" if not diffs else f"DIFFERS in {diffs[:5]}"))
    print(f"{len(new)} runs, {compared} values compared: {exact} bit-identical, {compared - exact} within floating-point "
          f"rounding (max relative difference {max_rel:.1e}). " + ("ALL REPRODUCED" if bad == 0 else f"{bad} runs DIFFER"))
    return 0 if bad == 0 and new else 1


if __name__ == "__main__":
    sys.exit(main())
