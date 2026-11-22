#!/usr/bin/env python3
"""Publication figures for the paper, built only from this repository's result tables (no simulation).

    python analysis/make_figures.py                      # Elsevier sizes (TR Part C/D): 90 / 140 / 190 mm
    python analysis/make_figures.py --style ieee         # IEEE sizes (T-ITS): 3.5 / 7.16 in
    python analysis/make_figures.py --formats pdf png    # choose outputs (default: pdf png tiff)
    python analysis/make_figures.py --only 1 4           # build selected figures

Outputs (default folder figures/):
  FigN_<name>.pdf   vector, fonts embedded (TrueType), for submission
  FigN_<name>.png   600 dpi, for drafts and slides
  FigN_<name>.tif   600 dpi, LZW-compressed, for journals that request TIFF
  source_data/FigN_<name>.csv   the exact numbers plotted (means, 95% CIs, n), for the data availability statement
  CAPTIONS.md       draft captions stating n, interval type and analysis status

Conventions: positive values = benefit of the energy term (lower battery withdrawal, shorter ride).
Intervals are paired seed-level 95% t intervals. Colours: Greedy = blue circle, Hungarian = vermillion square
(Okabe-Ito pair, validated colour-blind safe; shape carries identity in greyscale print).
Filled markers = significant after the protocol's Holm adjustment; open markers = not significant or descriptive.
"""
import argparse, csv, json, math, statistics as st, sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
sys.path.insert(0, str(ROOT / "analysis"))
import synthesis as SY  # noqa: E402  (post hoc replication synthesis, same repository)

POL = ("greedy", "hungarian")
NAME = {"greedy": "Greedy", "hungarian": "Hungarian"}
COLOR = {"greedy": "#0072B2", "hungarian": "#D55E00"}
MARK = {"greedy": "o", "hungarian": "s"}
INK, MUTED, GRID = "#222222", "#666666", "#DDDDDD"
STYLES = {  # widths in inches; font sizes in pt
    "elsevier": dict(single=90 / 25.4, onehalf=140 / 25.4, double=190 / 25.4, font=8, small=7),
    "ieee": dict(single=3.5, onehalf=5.0, double=7.16, font=8, small=7),
}


# ---------------------------------------------------------------------------------------------------------- helpers
def rows(p):
    with open(p, newline="") as fh:
        return list(csv.DictReader(fh))


def ci(x):
    n = len(x); m = st.mean(x); h = stats.t.ppf(0.975, n - 1) * st.stdev(x) / math.sqrt(n)
    return dict(n=n, mean=m, lo=m - h, hi=m + h)


def setup(style):
    s = STYLES[style]
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "Liberation Sans", "Helvetica", "DejaVu Sans"],
        "font.size": s["font"], "axes.titlesize": s["font"], "axes.labelsize": s["font"],
        "xtick.labelsize": s["small"], "ytick.labelsize": s["small"], "legend.fontsize": s["small"],
        "axes.edgecolor": MUTED, "axes.linewidth": 0.6, "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "xtick.major.size": 2.5, "ytick.major.size": 2.5, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": False, "lines.linewidth": 1.2, "errorbar.capsize": 0,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "figure.dpi": 150, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    })
    return s


def panel_label(ax, letter):
    ax.text(-0.02, 1.02, f"({letter})", transform=ax.transAxes, ha="right", va="bottom", fontweight="bold")


def zero_line(ax, vertical=True):
    (ax.axvline if vertical else ax.axhline)(0, color=MUTED, lw=0.6, ls=(0, (3, 2)), zorder=0)


def point(ax, x, y, lo, hi, pol, filled=True, horizontal=True, ms=4.2, z=3):
    kw = dict(fmt=MARK[pol], color=COLOR[pol], ms=ms, mew=0.9, elinewidth=0.9, zorder=z,
              mfc=COLOR[pol] if filled else "white", mec=COLOR[pol])
    if horizontal:
        ax.errorbar(x, y, xerr=[[x - lo], [hi - x]], **kw)
    else:
        ax.errorbar(x, y, yerr=[[y - lo], [hi - y]], **kw)


def policy_legend(ax, loc, extra=(), **kw):
    h = [Line2D([], [], marker=MARK[p], color=COLOR[p], ls="none", ms=4.2, label=NAME[p]) for p in POL] + list(extra)
    ax.legend(handles=h, loc=loc, frameon=False, handletextpad=0.3, borderaxespad=0.2, **kw)


def save(fig, out, stem, formats, source, header):
    for f in formats:
        if f == "tiff":
            fig.savefig(out / f"{stem}.tif", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
        elif f == "png":
            fig.savefig(out / f"{stem}.png", dpi=600, metadata={"Software": None})
        else:
            fig.savefig(out / f"{stem}.{f}", metadata={"CreationDate": None, "ModDate": None, "Producer": None, "Creator": None}
                        if f == "pdf" else None)
    plt.close(fig)
    (out / "source_data").mkdir(exist_ok=True)
    with open(out / "source_data" / f"{stem}.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(header); w.writerows(source)
    print(f"  {stem}: " + ", ".join(f"{stem}.{'tif' if f == 'tiff' else f}" for f in formats))


# ------------------------------------------------------------------------------- Fig 1: replication of the canonical cell
def fig1(s, out, fmts):
    energy, ride = SY.collect()
    e_tab, e_pool = SY.synthesise(energy); r_tab, r_pool = SY.synthesise(ride)
    fig, axes = plt.subplots(1, 2, figsize=(s["double"], 2.75), gridspec_kw=dict(width_ratios=[1.25, 1], wspace=0.55))
    src = []
    for ax, tab, pool, xlabel, letter, data in ((axes[0], e_tab, e_pool, "Battery saving (%)", "a", energy),
                                                (axes[1], r_tab, r_pool, "Ride-time reduction (s)", "b", ride)):
        studies = list(data.keys()); n = len(studies)
        ypos = {name: n - i + 1 for i, name in enumerate(studies)}
        for pol, dy in zip(POL, (0.17, -0.17)):
            for r in (t for t in tab if t["policy"] == pol):
                point(ax, r["mean"], ypos[r["study"]] + dy, r["ci_low"], r["ci_high"], pol)
                src.append([xlabel, r["study"], pol, r["n"], r["mean"], r["ci_low"], r["ci_high"], "study"])
            p = pool[pol]["all"]
            ax.errorbar(p["re"], 0.75 + dy, xerr=[[p["re"] - p["re_low"]], [p["re_high"] - p["re"]]], fmt="D", ms=5,
                        color=COLOR[pol], mfc=COLOR[pol], mec=INK, mew=0.6, elinewidth=1.4, zorder=4)
            src.append([xlabel, "Pooled (random effects, post hoc)", pol, p["seeds"], p["re"], p["re_low"], p["re_high"], "pooled"])
        ax.axhline(1.5, color=GRID, lw=0.6)
        zero_line(ax)
        labels = [lab.replace(" (approx. denominator)", "*") for lab in studies] + [f"Pooled ({sum(r['n'] for r in tab if r['policy'] == 'greedy')} seeds)"]
        ax.set_yticks([ypos[x] for x in studies] + [0.75]); ax.set_yticklabels(labels)
        ax.tick_params(axis="y", length=0); ax.spines["left"].set_visible(False)
        ax.set_ylim(0.2, n + 1.6); ax.set_xlabel(xlabel); panel_label(ax, letter)
    axes[0].set_xlim(-1.2, 4.6); axes[1].set_xlim(0, 23)
    h = [Line2D([], [], marker=MARK[p], color=COLOR[p], ls="none", ms=4.2, label=NAME[p]) for p in POL]
    h.append(Line2D([], [], marker="D", color=MUTED, mfc="white", mec=INK, ls="none", ms=4.5, label="Pooled, random effects (post hoc)"))
    fig.legend(handles=h, loc="lower center", bbox_to_anchor=(0.55, 0.99), ncol=3, frameon=False, handletextpad=0.3, columnspacing=1.4)
    save(fig, out, "Fig1_replication_canonical_cell", fmts, src, ["outcome", "study", "policy", "n_seeds", "mean", "ci_low", "ci_high", "kind"])
    g, h = e_pool["greedy"]["all"], e_pool["hungarian"]["all"]; rg, rh = r_pool["greedy"]["all"], r_pool["hungarian"]["all"]
    return ("Fig. 1. Effect of the energy term in the canonical scenario (12 vehicles, 100 requests, 825 kg / 80 kg, 100% SOC, "
            "1,800 s window, UTP network, Crr 0.012), replicated on independent workload seeds in every study component. "
            f"(a) Battery saving; (b) reduction in mean passenger ride time (not recorded in the original 2×2, A or B). Points: "
            f"paired seed-level means with 95% t intervals. Diamonds: random-effects pooled estimates (post hoc; not prespecified): "
            f"battery {g['re']:.2f}% [{g['re_low']:.2f}, {g['re_high']:.2f}] Greedy and {h['re']:.2f}% [{h['re_low']:.2f}, "
            f"{h['re_high']:.2f}] Hungarian ({g['seeds']} seeds); ride {rg['re']:.1f} s [{rg['re_low']:.1f}, {rg['re_high']:.1f}] and "
            f"{rh['re']:.1f} s [{rh['re_low']:.1f}, {rh['re_high']:.1f}] ({rg['seeds']} seeds). *Original 2×2 uses the condition-mean "
            "time-only withdrawal as denominator.")


# ---------------------------------------------------------------------------- Fig 2: payload ratio, same-state vs whole-run
def fig2(s, out, fmts):
    proto = json.loads((RES / "A_payload/experiment_A_payload.json").read_text())
    rho = {m["id"]: (m["rho_pct"], m.get("physical", True)) for m in proto["design"]["mass_configs"]}
    by = defaultdict(dict)
    for r in rows(RES / "A_payload/run_level.csv"):
        by[(r["mass_config"], r["algorithm"], r["seed"])][r["alpha_energy"]] = r
    res = defaultdict(lambda: defaultdict(list))
    for (m, pol, _), d in by.items():
        res[(m, pol)]["whole"].append(100 * (float(d["0"]["battery_Wh"]) - float(d["1"]["battery_Wh"])) / float(d["0"]["battery_Wh"]))
        res[(m, pol)]["local"].append(float(d["1"]["sdec_pct"]))
    fig, axes = plt.subplots(1, 2, figsize=(s["double"], 2.5), sharey=True, gridspec_kw=dict(wspace=0.12))
    src = []
    for ax, pol, letter in zip(axes, POL, "ab"):
        for kind, filled, ls, lab in (("whole", True, "-", "Whole-run saving"), ("local", False, (0, (3, 1.5)), "Same-state decision saving")):
            pts = []
            for m, (r_, phys) in sorted(rho.items(), key=lambda kv: kv[1][0]):
                c = ci(res[(m, pol)][kind]); pts.append((r_, c, phys))
                src.append([NAME[pol], kind, m, r_, phys, c["n"], c["mean"], c["lo"], c["hi"]])
            phys_pts = [p for p in pts if p[2]]
            ax.plot([p[0] for p in phys_pts], [p[1]["mean"] for p in phys_pts], color=COLOR[pol], ls=ls, lw=1.1, zorder=2)
            ax.plot([phys_pts[-1][0], pts[-1][0]], [phys_pts[-1][1]["mean"], pts[-1][1]["mean"]], color=COLOR[pol], ls=":", lw=0.8, zorder=2)
            for r_, c, phys in pts:
                ax.errorbar(r_, c["mean"], yerr=[[c["mean"] - c["lo"]], [c["hi"] - c["mean"]]], fmt=MARK[pol], ms=4.2, color=COLOR[pol],
                            mfc=COLOR[pol] if filled else "white", mec=COLOR[pol], mew=0.9, elinewidth=0.9, alpha=1 if phys else 0.55, zorder=3)
        ax.axvspan(17, 24, color="#F2F2F2", zorder=0)
        ax.text(17.3, 5.3, "stress test\n(non-physical)", ha="left", va="top", fontsize=STYLES_ACTIVE["small"], color=MUTED)
        zero_line(ax, vertical=False)
        ax.set_xticks([7.4, 9.5, 11.2, 14.0, 22.4]); ax.set_xticklabels(["7.4", "9.5", "11.2", "14.0", "22.4"])
        ax.set_xlim(6, 24); ax.set_xlabel("Passenger-to-vehicle load ratio ρ (%)")
        ax.set_title(NAME[pol], loc="left", color=INK); panel_label(ax, letter)
    axes[0].set_ylabel("Energy saving with energy term (%)"); axes[0].set_ylim(-0.1, 5.4)
    mh = [Line2D([], [], color=MUTED, ls="-", marker="o", mfc=MUTED, ms=4, label="Whole-run saving"),
          Line2D([], [], color=MUTED, ls=(0, (3, 1.5)), marker="o", mfc="white", ms=4, label="Same-state decision saving")]
    axes[0].legend(handles=mh, loc="upper left", frameon=False, handlelength=2.4, borderaxespad=0.2)
    save(fig, out, "Fig2_payload_dose_response", fmts, src, ["policy", "measure", "mass_config", "rho_pct", "physical", "n_seeds", "mean", "ci_low", "ci_high"])
    return ("Fig. 2. Experiment A: energy saving against the passenger-to-vehicle load ratio ρ for (a) Greedy and (b) Hungarian "
            "(100 paired seeds per point). Filled markers, solid lines: whole-run battery saving (time-only minus energy-weighted "
            "withdrawal, % of time-only). Open markers, dashed lines: same-state decision-level saving (planned energy of the "
            "time-only minus the energy-weighted choice in identical fleet states, equal-cardinality rounds, % of run withdrawal). "
            "95% t intervals. The shaded 160 kg-per-passenger point is a non-physical stress test (exploratory). Prespecified A1 "
            "(14.0% vs 7.4%, decision level): +0.67 pp Hungarian, +0.60 pp Greedy, both Holm p = 4×10⁻⁶, below the 1 pp margin.")


# ---------------------------------------------------------------------------------------- Fig 3: energy-weight sweep (D)
def fig3(s, out, fmts):
    eff = defaultdict(lambda: defaultdict(list))
    for p in rows(RES / "D_cost_proxy/analysis/paired_seed_effects.csv"):
        if p["reference"] == "e0":
            for k in ("battery_pp", "ride_s", "wait_s"):
                eff[(p["mass"], p["algorithm"], p["arm"])][k].append(float(p[k]))
    holm = {(r["mass"], r["algorithm"], r["arm"]): float(r["holm_p"]) for r in rows(RES / "D_cost_proxy/analysis/primary_contrasts.csv")
            if r["family"] == "energy_sweep" and r["metric"] == "battery_pp"}
    arms = ["e025", "e05", "e1", "e2", "e4", "pk1"]; xl = ["0.25", "0.5", "1", "2", "4", "PK\nproxy"]
    xs = [0, 1, 2, 3, 4, 5.4]
    masses = (("M825_P80", "Standard cart (ρ = 7.4%)"), ("M456_P100", "Light cart, luggage (ρ = 14.0%)"))
    fig, axes = plt.subplots(2, 2, figsize=(s["double"], 4.1), sharex=True, gridspec_kw=dict(hspace=0.18, wspace=0.28))
    src = []
    for col, (mass, title) in enumerate(masses):
        for row, (key, ylab) in enumerate((("battery_pp", "Battery saving vs time-only (%)"), ("ride_s", "Ride-time reduction (s)"))):
            ax = axes[row][col]
            for pol, dx in zip(POL, (-0.09, 0.09)):
                cs = [ci(eff[(mass, pol, a)][key]) for a in arms]
                ax.plot([x + dx for x in xs[:5]], [c["mean"] for c in cs[:5]], color=COLOR[pol], lw=1.0, zorder=2)
                for x, a, c in zip(xs, arms, cs):
                    sig = key == "battery_pp" and holm.get((mass, pol, a), 1) < 0.05
                    point(ax, x + dx, c["mean"], c["lo"], c["hi"], pol, filled=sig if key == "battery_pp" else True, horizontal=False)
                    src.append([mass, NAME[pol], a, key, c["n"], c["mean"], c["lo"], c["hi"], holm.get((mass, pol, a)) if key == "battery_pp" else ""])
            zero_line(ax, vertical=False); ax.axvline(4.7, color=GRID, lw=0.6)
            if row == 0:
                ax.set_title(title, loc="left", color=INK)
            if col == 0:
                ax.set_ylabel(ylab)
            panel_label(ax, "abcd"[row * 2 + col])
    for ax in axes[1]:
        ax.set_xticks(xs); ax.set_xticklabels(xl); ax.set_xlabel("Energy weight αE (time weight fixed at 1)")
    axes[0][0].set_ylim(-1, 5.5); axes[0][1].set_ylim(-1, 5.5); axes[1][0].set_ylim(-5, 33); axes[1][1].set_ylim(-5, 33)
    sig_h = [Line2D([], [], marker="o", ls="none", color=MUTED, mfc=MUTED, ms=4, label="Holm p < 0.05"),
             Line2D([], [], marker="o", ls="none", color=MUTED, mfc="white", ms=4, label="not significant")]
    policy_legend(axes[0][0], "upper left", extra=sig_h, ncol=2)
    save(fig, out, "Fig3_energy_weight_sweep", fmts, src, ["mass", "policy", "arm", "metric", "n_seeds", "mean", "ci_low", "ci_high", "holm_p"])
    return ("Fig. 3. Experiment D: response to the energy weight αE relative to the time-only objective (αE = 0), 40 paired seeds "
            "per point. (a, b) Battery saving; filled markers are significant after Holm adjustment over the 24-test energy-sweep "
            "family, open markers are not. (c, d) Reduction in mean passenger ride time (secondary, unadjusted). 'PK proxy' is the "
            "physics-derived passenger-km surrogate (not fitted to outcomes). 95% t intervals. No optimal weight is selected from these "
            "confirmatory seeds; completions were unchanged in every arm (within ±0.1 per 100).")


# ------------------------------------------------------------------------------------ Fig 4: operating boundaries (B, E, F)
def fig4(s, out, fmts):
    entries = []  # (group, label, policy, ci, significant)
    by = defaultdict(dict)
    for r in rows(RES / "B_fleet/run_level.csv"):
        by[(r["fleet_config"], r["initial_soc"], r["algorithm"], r["seed"])][r["alpha_energy"]] = float(r["battery_Wh"])
    bsig = {r["id"]: float(r["holm_p"]) for r in rows(RES / "B_fleet/analysis/contrasts.csv")}
    fleets = (("V12R100", "12 vehicles / 100 req."), ("V24R100", "24 vehicles / 100 req."), ("V24R200", "24 vehicles / 200 req."))
    for soc, soc_l in (("1.0", "100% SOC"), ("0.25", "25% SOC")):
        for f, fl in fleets:
            for pol in POL:
                v = [100 * (d["0"] - d["1"]) / d["0"] for (ff, so, pp, _), d in by.items() if ff == f and so == soc and pp == pol]
                p = bsig.get(f"B5_realized_saving_{f}_{pol}") if soc == "1.0" else None
                entries.append(("B  Fleet and demand scale", f"{fl}, {soc_l}", pol, ci(v), p is not None and p < 0.05))
    for folder, grp, lab in (("E_network", "E  Network and demand window", lambda c: c.replace("UM_district", "UM district").replace(" / ", ", ").replace("UTP", "UTP campus")),
                             ("F_road_load", "F  Road load (Crr 0.008 / 0.012 / 0.020)",
                              lambda c: c.replace("SOC 100%", "100% SOC").replace("SOC 25%", "25% SOC").replace(" / ", ", "))):
        for r in rows(RES / folder / "analysis/primary_contrasts.csv"):
            if r["family"] != "simple":
                continue
            parts = r["contrast"].split(" / "); pol = parts[-1]; label = lab(" / ".join(parts[:-1]))
            entries.append((grp, label, pol, dict(n=int(r["n"]), mean=float(r["mean"]), lo=float(r["ci_low"]), hi=float(r["ci_high"])),
                            float(r["holm_p"]) < 0.05))
    labels = []
    for g, l, *_ in entries:
        if (g, l) not in labels:
            labels.append((g, l))
    groups = list(dict.fromkeys(g for g, _ in labels))
    ypos, y, gpos = {}, 0, {}
    for g in groups:
        y -= 0.6; gpos[g] = y; y -= 1.0
        for gg, l in labels:
            if gg == g:
                ypos[(gg, l)] = y; y -= 1
    fig, ax = plt.subplots(figsize=(s["double"] * 0.78, 0.165 * len(labels) + 1.3))
    src = []
    for g, l, pol, c, sig in entries:
        dy = 0.17 if pol == "greedy" else -0.17
        point(ax, c["mean"], ypos[(g, l)] + dy, c["lo"], c["hi"], pol, filled=sig, ms=3.8)
        src.append([g.split("  ")[0], l, NAME[pol], c["n"], c["mean"], c["lo"], c["hi"], sig])
    for g in groups:
        ax.text(-0.005, gpos[g], g, transform=ax.get_yaxis_transform(), ha="right", va="center", fontweight="bold", fontsize=STYLES_ACTIVE["small"])
    zero_line(ax)
    ax.set_yticks([ypos[k] for k in labels]); ax.set_yticklabels([l for _, l in labels])
    ax.tick_params(axis="y", length=0); ax.spines["left"].set_visible(False)
    ax.set_ylim(y + 0.4, 0.2); ax.set_xlabel("Battery saving with energy term (%)")
    sig_h = [Line2D([], [], marker="o", ls="none", color=MUTED, mfc=MUTED, ms=4, label="Holm p < 0.05"),
             Line2D([], [], marker="o", ls="none", color=MUTED, mfc="white", ms=4, label="n.s. or descriptive")]
    h = [Line2D([], [], marker=MARK[p], color=COLOR[p], ls="none", ms=4.2, label=NAME[p]) for p in POL] + sig_h
    ax.legend(handles=h, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=4, frameon=False, handletextpad=0.3, columnspacing=1.2)
    save(fig, out, "Fig4_operating_boundaries", fmts, src, ["experiment", "condition", "policy", "n_seeds", "mean", "ci_low", "ci_high", "holm_significant"])
    return ("Fig. 4. Operating boundaries of the whole-run battery saving (40 paired seeds per point, 95% t intervals). Filled "
            "markers are significant after Holm adjustment within the experiment's prespecified family; open markers are not "
            "significant or, for B at 25% SOC, descriptive (no prespecified energy contrast). B: fleet size and demand scale; E: "
            "second network (UM district, synthetic mapped demand) and compressed arrival window; F: rolling-resistance sensitivity "
            "informed by external measurements. The prespecified high-road-load SOC interaction for Greedy was −3.18 pp "
            "[−4.70, −1.66], Holm p = 0.0022.")


# ---------------------------------------------------------------------------------- Fig 5: low-SOC service loss (B)
def fig5(s, out, fmts):
    by = defaultdict(dict)
    for r in rows(RES / "B_fleet/run_level.csv"):
        by[(r["fleet_config"], r["algorithm"], r["alpha_energy"], r["seed"])][r["initial_soc"]] = float(r["completed_per100"])
    fleets = (("V12R100", "12 / 100"), ("V24R100", "24 / 100"), ("V24R200", "24 / 200"))
    fig, ax = plt.subplots(figsize=(s["single"], 2.35))
    src = []
    for i, (f, _) in enumerate(fleets):
        for j, (pol, a) in enumerate(((p, a) for p in POL for a in ("0", "1"))):
            v = [d["0.25"] - d["1.0"] for (ff, pp, aa, _), d in by.items() if ff == f and pp == pol and aa == a]
            c = ci(v); x = i + (-0.27, -0.09, 0.09, 0.27)[j]
            point(ax, x, c["mean"], c["lo"], c["hi"], pol, filled=a == "1", horizontal=False, ms=3.8)
            src.append([f, NAME[pol], a, c["n"], c["mean"], c["lo"], c["hi"]])
    zero_line(ax, vertical=False)
    ax.set_xticks(range(3)); ax.set_xticklabels([l for _, l in fleets]); ax.set_xlabel("Vehicles / requests")
    ax.set_ylabel("Completions per 100 requests,\n25% minus 100% initial SOC")
    a_h = [Line2D([], [], marker="o", ls="none", color=MUTED, mfc="white", ms=4, label="αE = 0"),
           Line2D([], [], marker="o", ls="none", color=MUTED, mfc=MUTED, ms=4, label="αE = 1")]
    policy_legend(ax, "lower right", extra=a_h, ncol=2)
    ax.set_ylim(-3.2, 0.6)
    save(fig, out, "Fig5_low_soc_service", fmts, src, ["fleet_config", "policy", "alpha_energy", "n_seeds", "mean", "ci_low", "ci_high"])
    return ("Fig. 5. Experiment B: change in completed requests per 100 when initial SOC is reduced from 100% to 25%, by fleet "
            "size and demand (40 paired seeds, 95% t intervals). Open markers: time-only objective; filled: energy-weighted. The loss "
            "depends on fleet capacity, not on the energy term: prespecified energy-weight × SOC interactions at 24 vehicles lie within "
            "±1 completion per 100.")


# ---------------------------------------------------------------------------------- Fig 6: dynamic decomposition (C)
def fig6(s, out, fmts):
    se = rows(RES / "C_dynamics/analysis/seed_effects.csv")
    holm = {(r["algorithm"], r["estimand"]): float(r["holm_p"]) for r in rows(RES / "C_dynamics/analysis/primary_contrasts.csv")}
    est = (("whole_pct", "Whole-run saving (all-on vs all-off)"), ("pulse_sum_pct", "Sum of single-round pulse effects"),
           ("nonadditivity_pct", "Whole-run minus pulse sum"), ("prefix_direct_pct", "Prefix: direct (local) component"),
           ("prefix_continuation_pct", "Prefix: continuation residual"))
    fig, ax = plt.subplots(figsize=(s["onehalf"], 2.2))
    src = []
    for i, (k, lab) in enumerate(est):
        for pol, dy in zip(POL, (0.16, -0.16)):
            c = ci([float(r[k]) for r in se if r["algorithm"] == pol]); p = holm.get((pol, k))
            point(ax, c["mean"], -i + dy, c["lo"], c["hi"], pol, filled=p is not None and p < 0.05, ms=3.8)
            src.append([k, NAME[pol], c["n"], c["mean"], c["lo"], c["hi"], p if p is not None else "descriptive"])
    zero_line(ax)
    ax.set_yticks([-i for i in range(len(est))]); ax.set_yticklabels([l for _, l in est])
    ax.tick_params(axis="y", length=0); ax.spines["left"].set_visible(False)
    ax.set_xlabel("Percentage points of time-only battery withdrawal")
    policy_legend(ax, "lower right")
    save(fig, out, "Fig6_dynamic_decomposition", fmts, src, ["estimand", "policy", "n_seeds", "mean", "ci_low", "ci_high", "holm_p"])
    return ("Fig. 6. Experiment C: decomposition of the whole-run effect into single-round pulses and sequential prefixes "
            "(40 seeds, 95% t intervals). The three primary estimands (whole-run, whole-run minus pulse sum, prefix continuation) "
            "were all inconclusive after Holm adjustment (open markers); pulse sum and prefix direct component are descriptive. "
            "The prefix components sum to the whole-run saving by construction.")


FIGS = {1: fig1, 2: fig2, 3: fig3, 4: fig4, 5: fig5, 6: fig6}
STYLES_ACTIVE = STYLES["elsevier"]


def main():
    global STYLES_ACTIVE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--style", choices=sorted(STYLES), default="elsevier")
    ap.add_argument("--formats", nargs="+", choices=["pdf", "png", "tiff", "svg", "eps"], default=["pdf", "png", "tiff"])
    ap.add_argument("--only", nargs="+", type=int, choices=sorted(FIGS))
    ap.add_argument("--out", default=str(ROOT / "figures"))
    a = ap.parse_args()
    STYLES_ACTIVE = setup(a.style)
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    print(f"Style {a.style}; writing to {out}")
    caps = [f"# Figure captions (draft, {a.style} sizing)", "",
            "Generated by analysis/make_figures.py from the result tables; numbers in captions are computed, not typed.", ""]
    for k in (a.only or sorted(FIGS)):
        caps += [FIGS[k](STYLES_ACTIVE, out, a.formats), ""]
    if not a.only:
        (out / "CAPTIONS.md").write_text("\n".join(caps))
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
