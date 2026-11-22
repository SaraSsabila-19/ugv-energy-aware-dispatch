"""Publication figures (PDF + 300-dpi PNG) from run_level.csv and analysis/results.json. Needs matplotlib.

Figures written to OUT/analysis/figures/:
  contrasts_<family>.pdf/png   forest plot per family: paired mean contrast with 95% CI, margin band shaded
  A_dose_response.pdf/png      (if the protocol has mass levels) r, insertion changes, decision-level and realized saving vs rho
  B_service.pdf/png            (if the protocol has several fleet configs) completions per 100 by config x SOC x alpha, and 25% SOC loss
  realized_saving_per_seed.pdf/png  per-seed realized percent change of battery withdrawal (alpha_E 1 vs 0) by condition
usage: python bin/figures.py --protocol P.json --campaign OUT
"""
import argparse, collections, json, math
from pathlib import Path
import numpy as np
from scipy import stats
from .common import load_json
from .analyze import load_runs

OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]

def ci(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]; n = len(x)
    if n < 2: return (x.mean() if n else np.nan), np.nan
    return x.mean(), stats.t.ppf(0.975, n - 1) * x.std(ddof=1) / math.sqrt(n)

def setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42,
                         "ps.fonttype": 42, "axes.titlesize": 9, "legend.frameon": False, "figure.dpi": 100})
    return plt

def save(fig, d, name):
    for ext in ("pdf", "png"):
        fig.savefig(d / f"{name}.{ext}", dpi=300, bbox_inches="tight")

def forest(plt, results, d):
    fams = collections.defaultdict(list)
    for r in results["contrasts"]:
        if r["family"].endswith("descriptive"): continue
        fams[r["family"]].append(r)
    for fam, rs in fams.items():
        rs = [r for r in rs if not math.isnan(r.get("mean", float("nan")))]
        if not rs: continue
        fig, ax = plt.subplots(figsize=(6.5, 0.38 * len(rs) + 1.0))
        for i, r in enumerate(rs[::-1]):
            y = i
            if r["margin"]:
                ax.add_patch(plt.Rectangle((-r["margin"], y - 0.4), 2 * r["margin"], 0.8, color="0.9", zorder=0))
            ax.errorbar(r["mean"], y, xerr=[[r["mean"] - r["ci_low"]], [r["ci_high"] - r["mean"]]], fmt="o",
                        color=OKABE[0] if r.get("holm_p", 1) < 0.05 else "0.35", ms=4, capsize=2,
                        mfc=OKABE[0] if r.get("holm_p", 1) < 0.05 else "white")
        ax.axvline(0, color="0.5", lw=0.8)
        ax.set_yticks(range(len(rs))); ax.set_yticklabels([f"{r['id']}  [{r['unit']}]" for r in rs[::-1]], fontsize=7)
        ax.set_title(f"{results['protocol_id']} – {fam}: paired mean, 95% CI (filled: Holm p < 0.05; grey band: ± margin)", fontsize=8)
        save(fig, d, f"contrasts_{fam}"); plt.close(fig)

def pct_effect(data, fc, mc, alg, soc, seeds):
    a = data.get((fc, mc, alg, soc, 1.0), {}); b = data.get((fc, mc, alg, soc, 0.0), {})
    return [100 * (float(a[s]["battery_Wh"]) - float(b[s]["battery_Wh"])) / float(b[s]["battery_Wh"]) for s in seeds if s in a and s in b]

def dose(plt, protocol, data, d):
    mcs = protocol["design"]["mass_configs"]
    if len(mcs) < 2 or "rho_pct" not in mcs[0]: return
    fc = protocol["design"]["fleet_configs"][0]["id"]; seeds = sorted({s for v in data.values() for s in v})
    panels = [("r_within", "(a) Energy–duration correlation r"), ("insertion_change_pct", "(b) Insertion orders changed by αE (%)"),
              ("sdec_pct", "(c) Decision-level saving (% of run energy)"), ("realized", "(d) Realized withdrawal change, αE 1 vs 0 (%)")]
    fig, axs = plt.subplots(2, 2, figsize=(7.2, 5.4)); axs = axs.ravel()
    for ai, (key, title) in enumerate(panels):
        ax = axs[ai]
        for pi, alg in enumerate(protocol["design"]["algorithms"]):
            xs, ms, hs, phys = [], [], [], []
            for mc in mcs:
                if key == "realized":
                    vals = pct_effect(data, fc, mc["id"], alg, 1.0, seeds)
                else:
                    cell = data.get((fc, mc["id"], alg, 1.0, 1.0), {})
                    vals = [float(r[key]) for r in cell.values() if r.get(key, "") not in ("", None)]
                if not vals: continue
                m, h = ci(vals); xs.append(mc["rho_pct"] + (pi - 0.5) * 0.25); ms.append(m); hs.append(h); phys.append(mc.get("physical", True))
            if not xs: continue
            ph = [i for i, p in enumerate(phys) if p]
            ax.errorbar([xs[i] for i in ph], [ms[i] for i in ph], yerr=[hs[i] for i in ph], fmt="-o", color=OKABE[pi], ms=3.5, capsize=2, lw=1, label=alg)
            st = [i for i, p in enumerate(phys) if not p]
            if st:
                ax.errorbar([xs[i] for i in st], [ms[i] for i in st], yerr=[hs[i] for i in st], fmt="o", color=OKABE[pi], mfc="white", ms=4, capsize=2)
        if key == "realized": ax.axhline(0, color="0.6", lw=0.8)
        ax.set_title(title, fontsize=8.5, loc="left")
        if ai >= 2: ax.set_xlabel("Load ratio ρ (%)", fontsize=8)
    axs[0].legend(fontsize=7)
    fig.suptitle(f"{protocol['protocol_id']}: mean ± 95% CI over seeds; hollow markers = non-physical stress level", fontsize=8.5)
    fig.tight_layout(); save(fig, d, "A_dose_response"); plt.close(fig)

def fleet(plt, protocol, data, d):
    fcs = protocol["design"]["fleet_configs"]
    if len(fcs) < 2: return
    seeds = sorted({s for v in data.values() for s in v}); mc = protocol["design"]["mass_configs"][0]["id"]
    algs = protocol["design"]["algorithms"]
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1.5, 1]})
    ax = axs[0]; xt = []
    for fi, fc in enumerate(fcs):
        for si, soc in enumerate(protocol["design"]["initial_soc"]):
            for ai_, al in enumerate(protocol["design"]["alpha_energy"]):
                for pi, alg in enumerate(algs):
                    cell = data.get((fc["id"], mc, alg, soc, float(al)), {})
                    vals = [float(r["completed_per100"]) for r in cell.values()]
                    if not vals: continue
                    m, h = ci(vals); x = fi * 5 + si * 2 + ai_ * 0.7 + pi * 0.25
                    ax.errorbar(x, m, yerr=h, fmt="o" if al == 1 else "s", color=OKABE[pi], mfc=OKABE[pi] if al == 1 else "white", ms=3.5, capsize=2)
            xt.append((fi * 5 + si * 2 + 0.45, f"{fc['id']}\nSOC {int(soc*100)}%"))
    ax.set_xticks([x for x, _ in xt]); ax.set_xticklabels([t for _, t in xt], fontsize=6.5)
    ax.set_ylabel("Completed per 100 requests"); ax.set_title("(a) Service by configuration, SOC and αE", loc="left", fontsize=8.5)
    from matplotlib.lines import Line2D
    hs = [Line2D([], [], color=OKABE[i], marker="o", ls="", label=a_) for i, a_ in enumerate(algs)]
    hs += [Line2D([], [], color="0.3", marker="o", ls="", label="αE = 1"), Line2D([], [], color="0.3", marker="s", mfc="white", ls="", label="αE = 0")]
    ax.legend(handles=hs, fontsize=7, loc="lower right", ncol=2)
    ax = axs[1]
    for pi, alg in enumerate(algs):
        xs, ms, hs = [], [], []
        for fi, fc in enumerate(fcs):
            a = data.get((fc["id"], mc, alg, 0.25, 1.0), {}); b = data.get((fc["id"], mc, alg, 1.0, 1.0), {})
            vals = [float(a[s]["completed_per100"]) - float(b[s]["completed_per100"]) for s in seeds if s in a and s in b]
            if vals:
                m, h = ci(vals); xs.append(fi + pi * 0.12); ms.append(m); hs.append(h)
        ax.errorbar(xs, ms, yerr=hs, fmt="-o", color=OKABE[pi], ms=3.5, capsize=2, label=alg)
    ax.axhline(0, color="0.6", lw=0.8); ax.set_xticks(range(len(fcs))); ax.set_xticklabels([fc["id"] for fc in fcs])
    ax.set_ylabel("Completions per 100: 25% minus 100% SOC"); ax.set_title("(b) Low-SOC service loss at αE = 1", loc="left", fontsize=8.5); ax.legend(fontsize=7)
    fig.suptitle(f"{protocol['protocol_id']}: mean ± 95% CI over seeds", fontsize=8.5)
    fig.tight_layout(); fig.subplots_adjust(wspace=0.28); save(fig, d, "B_service"); plt.close(fig)

def per_seed(plt, protocol, data, d):
    seeds = sorted({s for v in data.values() for s in v}); D = protocol["design"]; items = []
    for fc in D["fleet_configs"]:
        for mc in D["mass_configs"]:
            for soc in D["initial_soc"]:
                for alg in D["algorithms"]:
                    v = pct_effect(data, fc["id"], mc["id"], alg, soc, seeds)
                    if v: items.append((f"{fc['id']} {mc['id']} SOC{int(soc*100)} {alg}", v))
    if not items: return
    fig, ax = plt.subplots(figsize=(6.5, 0.3 * len(items) + 1))
    rng = np.random.default_rng(0)
    for i, (lab, v) in enumerate(items):
        ax.scatter(v, i + rng.uniform(-0.15, 0.15, len(v)), s=5, color="0.55", lw=0)
        m, h = ci(v); ax.errorbar(m, i, xerr=h, fmt="o", color=OKABE[0], ms=4, capsize=2)
    ax.axvline(0, color="0.5", lw=0.8); ax.set_yticks(range(len(items))); ax.set_yticklabels([l for l, _ in items], fontsize=6.5)
    ax.set_xlabel("Realized change in battery withdrawal, αE 1 vs 0 (% per seed)")
    ax.set_title("Per-seed realized effects (grey) with mean and 95% CI (blue)")
    save(fig, d, "realized_saving_per_seed"); plt.close(fig)

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--protocol", required=True); ap.add_argument("--campaign", required=True)
    ap.add_argument("--repair", default=None, help="read run_level.csv and analysis/ from the repair folder")
    a = ap.parse_args(argv)
    from .probe import refuse_legacy_write
    refuse_legacy_write(Path(a.campaign).expanduser().resolve(), a.repair, 'figures')
    try:
        plt = setup()
    except ImportError:
        raise SystemExit("matplotlib is required for figures: $PY -m pip install matplotlib")
    protocol = load_json(a.protocol)
    camp = Path(a.repair).expanduser().resolve() if a.repair else Path(a.campaign).expanduser().resolve()
    data = load_runs(camp / "run_level.csv"); d = camp / "analysis" / "figures"; d.mkdir(parents=True, exist_ok=True)
    rf = camp / "analysis" / "results.json"
    if rf.exists():
        forest(plt, load_json(rf), d)
    dose(plt, protocol, data, d); fleet(plt, protocol, data, d); per_seed(plt, protocol, data, d)
    print("figures written to", d, sorted(p.name for p in d.glob("*.png")))
    return 0
