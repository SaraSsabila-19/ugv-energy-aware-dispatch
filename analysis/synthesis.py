"""Post hoc replication synthesis of the canonical baseline cell (NOT a prespecified analysis).

The canonical cell is the same specified scenario in every study: 12 vehicles, 100 requests, 825 kg empty / 80 kg per passenger,
100% initial SOC, 1,800 s arrival window, UTP campus network, BASE road load (Crr 0.012), alpha_E = 1 versus alpha_E = 0.
It was run on independent workload seeds in seven study components:

  Original 2x2 (40 seeds), A (100), B (40), C (40), D (40), E (40), F (40)  ->  340 paired seeds.

Each study is underpowered on its own for an effect of about 1.5-2% (40-seed standard errors are 0.5-0.8 pp). This script
summarises the seven estimates with fixed- and random-effects (DerSimonian-Laird) pooling, heterogeneity (Q, I^2, tau),
a leave-C-out sensitivity analysis and the minimum detectable effect of each study. It does not change any prespecified
verdict, and pooled p-values are deliberately not reported as confirmatory tests.

Outcomes
  energy:  battery saving (%), positive = lower battery withdrawal with the energy term. A/B are sign-reversed from their
           (alpha1 - alpha0) convention. The original 2x2 uses an approximate denominator: the condition mean alpha_E = 0
           withdrawal (per-seed alpha_E = 0 withdrawals are not in the archived summary).
  ride:    mean passenger ride time change (s), positive = shorter rides with the energy term. Available for C, D, E and F
           (A, B and the original 2x2 do not record ride time in their exported tables).

Inputs are the repository's own result tables (results/). Outputs go to analysis/output/.
Usage: python analysis/synthesis.py [--out DIR]   (default DIR: analysis/output; figures need matplotlib)
"""
import csv, json, math, re, statistics as st, sys
from collections import defaultdict
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
OUT = ROOT / "analysis" / "output"
POLICIES = ("greedy", "hungarian")


def rows(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


# ----------------------------------------------------------------------------------------------- per-study seed effects
def energy_original():
    md = (RES / "0_original_soc/results_2x2.md").read_text()
    alpha1_mean = {}
    for pol in POLICIES:   # "| greedy | 100% | 1 | 4000/4000 | 100.00 | 5795.9 | ..." -> alpha_E = 1 mean withdrawal
        m = re.search(rf"\|\s*{pol}\s*\|\s*100%\s*\|\s*1\s*\|[^|]*\|[^|]*\|\s*([0-9.]+)\s*\|", md)
        alpha1_mean[pol] = float(m.group(1))
    d = defaultdict(list)
    for r in rows(RES / "0_original_soc/paired_differences_by_seed.csv"):
        d[r["algorithm"]].append(float(r["D100_battery_Wh"]))          # alpha1 - alpha0, Wh, 100% SOC
    out = {}
    for pol in POLICIES:
        alpha0_mean = alpha1_mean[pol] - st.mean(d[pol])
        out[pol] = [-100.0 * x / alpha0_mean for x in d[pol]]
    return out


def energy_ab(path, cond):
    by = defaultdict(dict)
    for r in rows(path):
        if cond(r):
            by[(r["algorithm"], r["seed"])][r["alpha_energy"]] = float(r["battery_Wh"])
    out = defaultdict(list)
    for (pol, _), v in sorted(by.items()):
        out[pol].append(100.0 * (v["0"] - v["1"]) / v["0"])
    return out


def energy_c():
    out = defaultdict(list)
    for r in rows(RES / "C_dynamics/analysis/seed_effects.csv"):
        out[r["algorithm"]].append(float(r["whole_pct"]))
    return out


def ride_c():
    out = defaultdict(list)
    for r in rows(RES / "C_dynamics/analysis/seed_effects.csv"):
        out[r["algorithm"]].append(float(r["off_minus_on_ride_s"]))     # off - on: positive = shorter with energy term
    return out


def d_effects(metric):
    out = defaultdict(list)
    for r in rows(RES / "D_cost_proxy/analysis/paired_seed_effects.csv"):
        if r["mass"] == "M825_P80" and r["arm"] == "e1" and r["reference"] == "e0":
            out[r["algorithm"]].append(float(r[metric]))                # positive = lower battery / shorter ride
    return out


def ef_effects(path, cond, metric, sign):
    out = defaultdict(list)
    for r in rows(path):
        if cond(r):
            out[r["algorithm"]].append(sign * float(r[metric]))
    return out


def collect():
    energy = {
        "Original 2x2 (approx. denominator)": energy_original(),
        "A (payload)": energy_ab(RES / "A_payload/run_level.csv", lambda r: r["mass_config"] == "M825_P80"),
        "B (fleet)": energy_ab(RES / "B_fleet/run_level.csv",
                               lambda r: r["fleet_config"] == "V12R100" and r["initial_soc"] == "1.0"),
        "C (dynamics)": energy_c(),
        "D (cost proxy)": d_effects("battery_pp"),
        "E (network)": ef_effects(RES / "E_network/analysis/paired_seed_effects.csv",
                                  lambda r: r["network"] == "UTP" and r["window_s"] == "1800", "battery_saving_pct", 1),
        "F (road load)": ef_effects(RES / "F_road_load/analysis/paired_seed_effects.csv",
                                    lambda r: r["config"] == "BASE" and r["initial_soc"] == "1.0", "battery_saving_pct", 1),
    }
    ride = {
        "C (dynamics)": ride_c(),
        "D (cost proxy)": d_effects("ride_s"),
        "E (network)": ef_effects(RES / "E_network/analysis/paired_seed_effects.csv",
                                  lambda r: r["network"] == "UTP" and r["window_s"] == "1800", "ride_s_on_minus_off", -1),
        "F (road load)": ef_effects(RES / "F_road_load/analysis/paired_seed_effects.csv",
                                    lambda r: r["config"] == "BASE" and r["initial_soc"] == "1.0", "ride_s_on_minus_off", -1),
    }
    return energy, ride


# ---------------------------------------------------------------------------------------------------------- statistics
def study_summary(x):
    n = len(x); m = st.mean(x); sd = st.stdev(x); se = sd / math.sqrt(n); t = stats.t.ppf(0.975, n - 1)
    mde = (stats.norm.ppf(0.975) + stats.norm.ppf(0.80)) * se         # two-sided 5%, 80% power, normal approximation
    return dict(n=n, mean=m, sd=sd, se=se, ci_low=m - t * se, ci_high=m + t * se, mde80=mde)


def pool(studies):
    y = [s["mean"] for s in studies]; v = [s["se"] ** 2 for s in studies]; w = [1 / vi for vi in v]
    fe = sum(wi * yi for wi, yi in zip(w, y)) / sum(w); se_fe = math.sqrt(1 / sum(w))
    q = sum(wi * (yi - fe) ** 2 for wi, yi in zip(w, y)); k = len(y)
    c = sum(w) - sum(wi ** 2 for wi in w) / sum(w); tau2 = max(0.0, (q - (k - 1)) / c)
    wr = [1 / (vi + tau2) for vi in v]; re_ = sum(wi * yi for wi, yi in zip(wr, y)) / sum(wr); se_re = math.sqrt(1 / sum(wr))
    z = stats.norm.ppf(0.975)
    return dict(k=k, seeds=sum(s["n"] for s in studies), fe=fe, fe_low=fe - z * se_fe, fe_high=fe + z * se_fe,
                re=re_, re_low=re_ - z * se_re, re_high=re_ + z * se_re, q=q, q_df=k - 1, q_p=float(stats.chi2.sf(q, k - 1)),
                i2=max(0.0, (q - (k - 1)) / q) * 100 if q > 0 else 0.0, tau=math.sqrt(tau2))


def synthesise(data):
    table, pooled = [], {}
    for pol in POLICIES:
        studies = []
        for name, eff in data.items():
            s = study_summary(eff[pol]); s.update(study=name, policy=pol); studies.append(s); table.append(s)
        pooled[pol] = {"all": pool(studies),
                       "without_C": pool([s for s in studies if not s["study"].startswith("C ")])}
        # outlier diagnostic: each study against the inverse-variance mean of the others
        for s in studies:
            rest = [o for o in studies if o is not s]
            w = [1 / o["se"] ** 2 for o in rest]; m = sum(wi * o["mean"] for wi, o in zip(w, rest)) / sum(w)
            s["z_vs_others"] = (s["mean"] - m) / math.sqrt(s["se"] ** 2 + 1 / sum(w))
    return table, pooled


# -------------------------------------------------------------------------------------------------------------- output
def write_csv(path, table):
    cols = ["policy", "study", "n", "mean", "sd", "se", "ci_low", "ci_high", "mde80", "z_vs_others"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in table:
            w.writerow({k: (f"{r[k]:.6f}" if isinstance(r[k], float) else r[k]) for k in cols})


def forest(path_stem, table, pooled, unit, title):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: figures skipped"); return
    fig, axes = plt.subplots(1, 2, figsize=(10, 0.45 * (len(table) // 2) + 2.2), sharey=True, sharex=True)
    for ax, pol in zip(axes, POLICIES):
        st_ = [r for r in table if r["policy"] == pol]; ys = list(range(len(st_) + 1, 1, -1))
        for y, r in zip(ys, st_):
            ax.errorbar(r["mean"], y, xerr=[[r["mean"] - r["ci_low"]], [r["ci_high"] - r["mean"]]], fmt="s", color="#3a6ea5",
                        ms=4 + r["n"] / 40, capsize=2, lw=1)
        p = pooled[pol]["all"]
        ax.errorbar(p["re"], 0.6, xerr=[[p["re"] - p["re_low"]], [p["re_high"] - p["re"]]], fmt="D", color="#b03a2e", ms=7, capsize=3)
        ax.axvline(0, color="0.5", lw=0.8, ls="--")
        ax.set_title(pol.capitalize(), fontsize=10); ax.set_xlabel(unit, fontsize=9)
        ax.set_yticks(ys + [0.6]); ax.set_yticklabels([r["study"] for r in st_] + [f"Pooled RE ({p['seeds']} seeds)"], fontsize=8)
        ax.tick_params(axis="x", labelsize=8)
    fig.suptitle(title, fontsize=10); fig.tight_layout()
    fig.savefig(OUT / f"{path_stem}.png", dpi=200, metadata={"Software": None})
    fig.savefig(OUT / f"{path_stem}.pdf", metadata={"CreationDate": None, "ModDate": None, "Producer": None, "Creator": None})
    plt.close(fig)


def fmt(p):
    return (f"{p['re']:.2f} [{p['re_low']:.2f}, {p['re_high']:.2f}]; FE {p['fe']:.2f}; "
            f"Q = {p['q']:.1f} (df {p['q_df']}, p = {p['q_p']:.3f}); I² = {p['i2']:.0f}%; tau = {p['tau']:.2f}")


def main():
    global OUT
    if "--out" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--out") + 1]).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    energy, ride = collect()
    e_table, e_pool = synthesise(energy); r_table, r_pool = synthesise(ride)
    write_csv(OUT / "synthesis_energy_by_study.csv", e_table); write_csv(OUT / "synthesis_ride_by_study.csv", r_table)
    summary = {"label": "POST HOC replication synthesis; not prespecified; does not alter any protocol verdict",
               "energy_saving_pct": e_pool, "ride_time_reduction_s": r_pool}
    (OUT / "synthesis_pooled.json").write_text(json.dumps(summary, indent=2))
    forest("forest_energy", e_table, e_pool, "Battery saving with energy term (%)",
           "Canonical cell, seven independent seed sets (95% t CIs; pooled random-effects, post hoc)")
    forest("forest_ride", r_table, r_pool, "Ride-time reduction with energy term (s)",
           "Canonical cell, passenger ride time (95% t CIs; pooled random-effects, post hoc)")
    md = ["# Post hoc replication synthesis of the canonical cell", "",
          "Not prespecified. Summarises the identically specified baseline cell (12 vehicles, 100 requests, standard mass, "
          "100% SOC, 1,800 s window, UTP network, BASE road load; alpha_E 1 vs 0) across independent seed sets. "
          "Prespecified verdicts in each study are unchanged. Pooled intervals are random-effects (DerSimonian-Laird) 95% "
          "normal intervals; study intervals are 95% t intervals. MDE80 = minimum detectable effect at 80% power.", ""]
    for label, table, pooled, unit in (("Battery saving (%)", e_table, e_pool, "%"), ("Ride-time reduction (s)", r_table, r_pool, "s")):
        md += [f"## {label}", "", "| Policy | Study | Seeds | Mean | 95% CI | MDE80 | z vs others |", "|---|---|---:|---:|---|---:|---:|"]
        for r in table:
            md.append(f"| {r['policy']} | {r['study']} | {r['n']} | {r['mean']:.2f} | [{r['ci_low']:.2f}, {r['ci_high']:.2f}] | "
                      f"{r['mde80']:.2f} | {r['z_vs_others']:+.2f} |")
        md.append("")
        for pol in POLICIES:
            md.append(f"- **{pol}**, all studies: {fmt(pooled[pol]['all'])}")
            md.append(f"- **{pol}**, excluding C: {fmt(pooled[pol]['without_C'])}")
        md.append("")
    md += ["Notes: the original 2x2 uses the condition-mean alpha_E = 0 withdrawal as denominator. Experiment C's references were "
           "verified identical to native simulator runs (verification/c_native_reference_check), so C's estimate reflects seed "
           "sampling. Ride time is not available for the original 2x2, A or B."]
    (OUT / "SYNTHESIS.md").write_text("\n".join(md) + "\n")
    for pol in POLICIES:
        print(f"energy {pol:9s} {fmt(e_pool[pol]['all'])}")
        print(f"ride   {pol:9s} {fmt(r_pool[pol]['all'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
