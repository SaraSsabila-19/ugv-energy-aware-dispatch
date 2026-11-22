"""Recompute the sample-size justification from your existing 320-run energy-weight x SOC campaign (kit v1/v2 layout:
S4_<alg>_seed<seed>_soc<100|25>_a<0|1>/results/<id>/run_summary.csv). Needs numpy and scipy.
usage: python bin/sample_size.py --existing /path/to/energy_soc_campaign_runs
"""
import argparse, csv, glob, math, os, re
import numpy as np
from scipy import stats

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--existing", required=True); a = ap.parse_args(argv)
    R = {}
    for f in glob.glob(os.path.join(os.path.expanduser(a.existing), "S4_*", "results", "*", "run_summary.csv")):
        m = re.search(r"S4_(\w+?)_seed(\d+)_soc(\d+)_a(\d)", f)
        if not m: continue
        r = next(csv.DictReader(open(f)))
        R[(m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)))] = (float(r["total_battery_withdrawn_Wh"]), int(r["completed_requests"]))
    seeds = sorted({k[1] for k in R}); print(f"{len(R)} runs, {len(seeds)} seeds read from {a.existing}")
    if not R: return 1
    def hw(sd, n): return stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n)
    def mde(sd, n, alpha=0.0125, power=0.8): return (stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)) * sd / math.sqrt(n)
    print("\nExperiment A (realized percent change of withdrawal, 100% SOC; contrast of two independent levels => SD*sqrt(2))")
    for alg in ("hungarian", "greedy"):
        d = [100 * (R[(alg, s, 100, 1)][0] - R[(alg, s, 100, 0)][0]) / R[(alg, s, 100, 0)][0] for s in seeds if (alg, s, 100, 1) in R and (alg, s, 100, 0) in R]
        sd = np.std(d, ddof=1); sc = sd * math.sqrt(2)
        print(f"  {alg}: per-seed SD {sd:.2f} pp -> contrast SD {sc:.2f} pp")
        for n in (40, 60, 100, 150):
            print(f"     n={n:3d}: 95% CI half-width {hw(sc, n):.2f} pp; detectable difference (80% power, Holm alpha 0.0125) {mde(sc, n):.2f} pp")
    print("\nExperiment B (completions per 100 requests)")
    for alg in ("hungarian", "greedy"):
        I = [(R[(alg, s, 25, 1)][1] - R[(alg, s, 25, 0)][1]) - (R[(alg, s, 100, 1)][1] - R[(alg, s, 100, 0)][1]) for s in seeds if all((alg, s, x, y) in R for x in (25, 100) for y in (0, 1))]
        L = [R[(alg, s, 25, 1)][1] - R[(alg, s, 100, 1)][1] for s in seeds if (alg, s, 25, 1) in R and (alg, s, 100, 1) in R]
        sdI, sdL = np.std(I, ddof=1), np.std(L, ddof=1)
        print(f"  {alg}: interaction SD {sdI:.2f}; 25% SOC loss SD {sdL:.2f} (DiD with a near-zero-loss configuration: SD about {sdL:.2f})")
        for n in (30, 40, 60):
            print(f"     n={n}: interaction CI half-width {hw(sdI, n):.2f}; loss-contrast half-width {hw(sdL, n):.2f}; detectable loss change {mde(sdL, n):.2f}")
    return 0
