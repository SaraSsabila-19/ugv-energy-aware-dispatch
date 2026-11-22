"""Protocol-driven paired analysis. Requires numpy and scipy (already in the simulator environment).

Each contrast in the protocol is a weighted sum of per-seed terms:
  {"w": w, "cell": {...}}                          -> w * Y(cell)
  {"w": w, "type": "pctdiff", "outcome": o, "a": {...}, "b": {...}}  -> w * 100*(Y_o(a)-Y_o(b))/Y_o(b)
Cells name fleet_config, mass_config, algorithm, initial_soc, alpha_energy. Seeds missing any cell are dropped (reported).
Outputs: contrasts.csv, contrasts.md, condition_summary.csv/.md, results.json in the campaign's analysis/ folder.
usage: python bin/analyze.py --protocol P.json --campaign OUT [--repair REPAIR_DIR] [--run-level FILE] [--mc 1000000]
With --repair, run_level.csv is read from, and analysis/ written to, the repair folder.
"""
import argparse, csv, json, math, collections
from pathlib import Path
import numpy as np
from scipy import stats
from .common import load_json, write_json

KEYS = ("fleet_config", "mass_config", "algorithm", "initial_soc", "alpha_energy")

def ckey(c):
    return (c["fleet_config"], c["mass_config"], c["algorithm"], float(c["initial_soc"]), float(c["alpha_energy"]))

def load_runs(path):
    data = collections.defaultdict(dict)
    with open(path) as f:
        for r in csv.DictReader(f):
            k = (r["fleet_config"], r["mass_config"], r["algorithm"], float(r["initial_soc"]), float(r["alpha_energy"]))
            data[k][int(r["seed"])] = r
    return data

def val(data, cell, seed, outcome):
    r = data.get(ckey(cell), {}).get(seed)
    if r is None or r.get(outcome, "") in ("", None):
        return None
    v = float(r[outcome])
    return None if math.isnan(v) else v

def contrast_values(data, con, seeds):
    out = {}
    for s in seeds:
        tot = 0.0; ok = True
        for t in con["terms"]:
            if t.get("type") == "pctdiff":
                a = val(data, t["a"], s, t["outcome"]); b = val(data, t["b"], s, t["outcome"])
                if a is None or b is None or b == 0: ok = False; break
                tot += t["w"] * 100.0 * (a - b) / b
            else:
                v = val(data, t["cell"], s, con["outcome"])
                if v is None: ok = False; break
                tot += t["w"] * v
        if ok: out[s] = tot
    return out

def signflip(d, mc, rng):
    d = np.asarray(d, float); n = len(d); obs = abs(d.sum())
    if n == 0: return float("nan"), "none"
    if np.allclose(d, 0): return 1.0, "exact"
    for sc in (1, 2, 4, 5, 10, 20, 100):
        x = d * sc
        if np.allclose(x, np.round(x), atol=1e-9) and np.abs(np.round(x)).sum() < 2e6:
            dist = {0: 1}
            for v in np.round(x).astype(np.int64):
                nd = collections.defaultdict(int)
                for s_, c in dist.items(): nd[s_ + v] += c; nd[s_ - v] += c
                dist = nd
            o = round(obs * sc)
            return sum(c for s_, c in dist.items() if abs(s_) >= o) / 2.0 ** n, "exact"
    if n <= 20:
        signs = ((np.arange(2 ** n)[:, None] >> np.arange(n)) & 1) * 2 - 1
        return float(np.mean(np.abs(signs @ d) >= obs - 1e-12)), "exact"
    hits = 0; done = 0
    while done < mc:
        m = min(200000, mc - done); e = rng.choice([-1.0, 1.0], size=(m, n)); hits += int(np.sum(np.abs(e @ d) >= obs - 1e-12)); done += m
    return (hits + 1) / (mc + 1), "monte-carlo"

def holm(ps):
    ps = np.asarray(ps, float); m = len(ps); order = np.argsort(ps); adj = np.empty(m); run = 0.0
    for i, j in enumerate(order):
        run = max(run, min(1.0, (m - i) * ps[j])); adj[j] = run
    return adj

def classify(holm_p, lo, hi, margin):
    sig = holm_p < 0.05
    if margin is None:
        return "significant" if sig else "not significant"
    inside = (-margin < lo) and (hi < margin)
    if sig and not inside and (lo >= margin or hi <= -margin):
        return "effect exceeding margin"
    if sig and inside:
        return "detectable but below margin"
    if sig:
        return "significant; size relative to margin unresolved"
    if inside:
        return "no effect larger than margin"
    return "inconclusive"

def summarize_conditions(data):
    rows = []
    for k in sorted(data):
        rs = list(data[k].values())
        g = lambda c: np.array([float(r[c]) for r in rs if r.get(c, "") not in ("", None)], float)
        done = g("completed").sum(); req = sum(int(r["requests"]) for r in rs); bat = g("battery_Wh")
        E, T, C = g("r_E_ss").sum(), g("r_T_ss").sum(), g("r_cross").sum()
        rows.append({"fleet_config": k[0], "mass_config": k[1], "algorithm": k[2], "initial_soc": k[3], "alpha_energy": k[4], "runs": len(rs),
                     "completed": int(done), "requests": req, "fulfil_pct": 100 * done / req if req else float("nan"),
                     "battery_Wh_mean": bat.mean(), "wh_per_completion": bat.sum() / done if done else float("nan"),
                     "km_mean": g("km").mean(), "wait_s_mean": g("wait_s").mean(), "blocked_pairs_mean": g("blocked_pairs").mean(),
                     "r_within_pooled": C / math.sqrt(E * T) if E > 0 and T > 0 else float("nan"),
                     "matching_change_pct_mean": g("matching_change_pct").mean() if len(g("matching_change_pct")) else float("nan"),
                     "insertion_change_pct_mean": g("insertion_change_pct").mean() if len(g("insertion_change_pct")) else float("nan"),
                     "sdec_pct_mean": g("sdec_pct").mean() if len(g("sdec_pct")) else float("nan"),
                     "pooling_ratio_mean": g("pooling_ratio").mean(),
                     "unequal_cardinality_rounds_total": int(g("rounds_cardinality_differs").sum()) if len(g("rounds_cardinality_differs")) else 0,
                     "runs_with_unequal_rounds": int((g("rounds_cardinality_differs") > 0).sum()) if len(g("rounds_cardinality_differs")) else 0,
                     "compared_energy_share_pct_min": g("compared_energy_share_pct").min() if len(g("compared_energy_share_pct")) else float("nan"),
                     "probe_accounting_not_pass": sum(1 for r in rs if r.get("probe_accounting") not in (None, "", "PASS"))})
    return rows

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--protocol", required=True); ap.add_argument("--campaign", required=True)
    ap.add_argument("--run-level", default=None); ap.add_argument("--mc", type=int, default=1_000_000)
    ap.add_argument("--repair", default=None)
    ap.add_argument("--rng-seed", type=int, default=20261120)
    a = ap.parse_args(argv)
    from .probe import refuse_legacy_write
    refuse_legacy_write(Path(a.campaign).expanduser().resolve(), a.repair, 'analyze')
    protocol = load_json(a.protocol)
    camp = Path(a.repair).expanduser().resolve() if a.repair else Path(a.campaign).expanduser().resolve()
    rl = Path(a.run_level) if a.run_level else camp / "run_level.csv"
    data = load_runs(rl); outdir = camp / "analysis"; outdir.mkdir(exist_ok=True)
    seeds = sorted({s for d in data.values() for s in d})
    rng = np.random.default_rng(a.rng_seed)
    res = []
    for con in protocol.get("contrasts", []):
        v = contrast_values(data, con, seeds); d = np.array(list(v.values()), float); n = len(d)
        if n < 2:
            res.append({**{k: con[k] for k in ("id", "family", "outcome", "unit", "margin", "prediction")}, "n": n, "mean": float("nan"),
                        "ci_low": float("nan"), "ci_high": float("nan"), "sd": float("nan"), "d_z": float("nan"), "p": float("nan"), "p_method": "none"})
            continue
        m = d.mean(); sd = d.std(ddof=1); se = sd / math.sqrt(n); h = stats.t.ppf(0.975, n - 1) * se
        p, how = signflip(d, a.mc, rng)
        res.append({**{k: con[k] for k in ("id", "family", "outcome", "unit", "margin", "prediction")}, "n": n, "mean": m,
                    "ci_low": m - h, "ci_high": m + h, "sd": sd, "d_z": m / sd if sd > 0 else float("nan"), "p": p, "p_method": how,
                    "per_seed": {str(k): x for k, x in v.items()}})
    fam = collections.defaultdict(list)
    for i, r in enumerate(res): fam[r["family"]].append(i)
    for f, idx in fam.items():
        ps = [res[i]["p"] if not math.isnan(res[i]["p"]) else 1.0 for i in idx]
        adj = holm(ps)
        for i, q in zip(idx, adj):
            res[i]["holm_p"] = float(q); res[i]["family_size"] = len(idx)
            res[i]["verdict"] = classify(q, res[i]["ci_low"], res[i]["ci_high"], res[i]["margin"]) if not math.isnan(res[i]["mean"]) else "no data"
    cols = ["family", "id", "outcome", "unit", "n", "mean", "ci_low", "ci_high", "sd", "d_z", "p", "p_method", "holm_p", "family_size", "margin", "verdict", "prediction"]
    with open(outdir / "contrasts.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); [w.writerow(r) for r in res]
    fmt = lambda x: "" if x is None else (f"{x:.4g}" if isinstance(x, float) else str(x))
    md = [f"# Contrasts: {protocol['protocol_id']}", "", f"Seeds available: {len(seeds)}. Holm adjustment within each family.", ""]
    for f in sorted(fam):
        md += [f"## {f}", "", "| Contrast | n | Mean | 95% CI | SD | d_z | p (method) | Holm p | Margin | Verdict |", "|---|---|---|---|---|---|---|---|---|---|"]
        for i in fam[f]:
            r = res[i]
            md.append(f"| {r['id']} | {r['n']} | {fmt(r['mean'])} {r['unit']} | [{fmt(r['ci_low'])}, {fmt(r['ci_high'])}] | {fmt(r['sd'])} | {fmt(r['d_z'])} | "
                      f"{fmt(r['p'])} ({r['p_method']}) | {fmt(r.get('holm_p'))} | {fmt(r['margin'])} | {r.get('verdict','')} |")
        md.append("")
    (outdir / "contrasts.md").write_text("\n".join(md))
    summ = summarize_conditions(data)
    with open(outdir / "condition_summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summ[0].keys())); w.writeheader(); [w.writerow(r) for r in summ]
    md2 = ["| " + " | ".join(summ[0].keys()) + " |", "|" + "---|" * len(summ[0])]
    md2 += ["| " + " | ".join(fmt(v) if isinstance(v, float) else str(v) for v in r.values()) + " |" for r in summ]
    (outdir / "condition_summary.md").write_text("\n".join(md2))
    write_json(outdir / "results.json", {"protocol_id": protocol["protocol_id"], "seeds": seeds, "contrasts": res, "conditions": summ,
                                         "mc_draws": a.mc, "rng_seed": a.rng_seed})
    print("\n".join(md))
    return 0
