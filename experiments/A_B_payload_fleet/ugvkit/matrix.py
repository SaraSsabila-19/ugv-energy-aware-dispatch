"""Show the run matrix of a protocol, progress in a campaign folder, and estimated compute.
usage: python bin/matrix.py --protocol P.json [--campaign OUT] [--jobs N] [--write-csv runs.csv]
"""
import argparse, collections, csv, os
from pathlib import Path
from .common import expand_protocol, load_json

# Measured wall seconds per run (probe enabled) on a 2-core cloud VM with CPython 3.13, Nov 2026. Scale for your CPU.
SEC = {(12, 100): 11.0, (24, 100): 11.5, (24, 200): 20.0}

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--protocol", required=True); ap.add_argument("--campaign", default=None)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1)); ap.add_argument("--write-csv", default=None)
    a = ap.parse_args(argv)
    p = load_json(a.protocol); specs = expand_protocol(p)
    by = collections.Counter((s["fleet_config"], s["mass_config"], s["algorithm"], s["initial_soc"], s["alpha_energy"]) for s in specs)
    seeds = sorted({s["seed"] for s in specs})
    print(f"{p['protocol_id']}: {len(specs)} runs = {len(by)} conditions x {len(seeds)} seeds ({seeds[0]}..{seeds[-1]})")
    done = 0
    if a.campaign:
        done = sum(1 for s in specs if (Path(a.campaign) / "runs" / s["label"] / "RUN_OK.json").exists())
        print(f"complete: {done}, remaining: {len(specs) - done}")
    rem = [s for s in specs if not (a.campaign and (Path(a.campaign) / "runs" / s["label"] / "RUN_OK.json").exists())]
    cpu = sum(SEC.get((s["vehicles"], s["requests"]), 20.0) for s in rem)
    print(f"estimated CPU time remaining: {cpu/3600:.1f} core-hours; wall time with {a.jobs} parallel jobs: about {cpu/a.jobs/3600:.1f} h"
          " (reference machine; expect 0.5-1.5x on a modern desktop)")
    print(f"disk: about 2.5 MB per run, so about {len(specs)*2.5/1024:.1f} GB for the full campaign folder")
    if a.write_csv:
        with open(a.write_csv, "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(["label", "seed", "fleet_config", "mass_config", "algorithm", "initial_soc", "alpha_energy", "overrides"])
            for s in specs: w.writerow([s["label"], s["seed"], s["fleet_config"], s["mass_config"], s["algorithm"], s["initial_soc"], s["alpha_energy"], s["overrides"]])
        print("wrote", a.write_csv)
    return 0
