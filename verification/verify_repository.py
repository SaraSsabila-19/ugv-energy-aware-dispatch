"""Verify the reproducibility package end to end, without running the simulator (about 1 minute).

Checks
  1  frozen simulator and input hashes
  2  every experiment kit is byte-identical to its archived kit zip, and its own KIT_SHA256SUMS passes
  3  archive checksums (archives/ARCHIVES.sha256)
  4  every file in results/ is byte-identical to the same member of its archive (results were not edited)
  5  the protocol in each kit is identical to the protocol recorded with its results
  6  statistics recomputed independently from run-level data:
       A/B: all 66 prespecified contrasts (mean and 95% t CI) from run_level.csv and the protocol definitions
       C:   seed-level whole-run savings from reference runs; 6 primary contrasts (mean, CI)
       D:   all paired seed effects from run_level.csv; all 40 primary rows (mean, CI)
       E/F: all paired seed effects from run_level.csv; all simple and interaction contrasts (mean, CI)
       Holm-adjusted p-values recomputed from the reported raw p-values within each family
  7  the Experiment C native reference check (16 runs) is identical
  8  the post hoc synthesis reproduces analysis/output exactly

Sign-flip p-values are not recomputed here (Monte Carlo, protocol-seeded); each kit's own analysis code regenerates them.
Usage: python verification/verify_repository.py      (exit code 0 = all checks passed)
"""
import csv, hashlib, io, json, math, re, statistics as st, subprocess, sys, tempfile, zipfile
from collections import defaultdict
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
FROZEN = {"src/frozen/app.py": "7b52bb550414469937da3098f91313b366137d43bd48b8465b840a97bffeb0a0",
          "inputs/utp_graph.graphml": "ebd138a83763f11172e079f40457b371be7eebcd2e3aa018aeda13d9d70114f4",
          "inputs/hotspot_locations.csv": "6a55a275f2ac18ab383d2efcd67a31250602503a62fa3c5bf2f3f504ae0b979d"}
KITS = {"0_original_soc": "energy_soc_experiment_kit_v2.zip", "A_B_payload_fleet": "energy_soc_experiment_kit_v3.1.zip",
        "C_dynamics": "energy_soc_experiment_kit_v4.zip", "D_cost_proxy": "energy_soc_experiment_kit_v5.zip",
        "E_network": "energy_soc_experiment_kit_v6.zip", "F_road_load": "energy_soc_experiment_kit_v7.zip"}
RESULTS = {"A_payload": "EXP_A_PAYLOAD_20261121T152221.zip", "B_fleet": "EXP_B_FLEET_repaired_20261121T051808.zip",
           "C_dynamics": "EXP_C_IMPULSE_20261122T073630.zip", "D_cost_proxy": "EXP_D_EQUIVALENCE_20261122T124719.zip",
           "E_network": "EXP_E_NETWORK_20261122T165310_397512.zip", "F_road_load": "EXP_F_ROAD_LOAD_20261122T165338_661310.zip"}
PROTOCOLS = [("A_B_payload_fleet/protocols/experiment_A_payload.json", "A_payload/experiment_A_payload.json"),
             ("A_B_payload_fleet/protocols/experiment_B_fleet.json", "B_fleet/experiment_B_fleet.json"),
             ("C_dynamics/protocols/experiment_C.json", "C_dynamics/protocol.json"),
             ("D_cost_proxy/protocols/experiment_D.json", "D_cost_proxy/protocol.json"),
             ("E_network/protocols/experiment_E.json", "E_network/protocol.json"),
             ("F_road_load/protocols/experiment_F.json", "F_road_load/protocol.json")]
TOL = 1e-9

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""), flush=True)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rows(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def close(a, b, tol=TOL):
    a, b = float(a), float(b)
    if math.isnan(a) and math.isnan(b):
        return True
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def summary(x):
    n = len(x); m = st.mean(x); se = st.stdev(x) / math.sqrt(n); t = stats.t.ppf(0.975, n - 1)
    return n, m, m - t * se, m + t * se


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i]); out = [0.0] * len(ps); run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i])); out[i] = run
    return out


def check_holm(name, table, family_key, p_key="p", h_key="holm_p"):
    fam = defaultdict(list)
    for r in table:
        if r.get(p_key) not in ("", None) and r.get(h_key) not in ("", None) and not math.isnan(float(r[p_key])):
            fam[family_key(r)].append(r)
    bad = 0
    for _, rs in fam.items():
        for r, h in zip(rs, holm([float(r[p_key]) for r in rs])):
            bad += not close(h, r[h_key], 1e-9)
    check(f"{name}: Holm adjustment within {len(fam)} families", bad == 0, f"{bad} mismatches" if bad else "")


# ----------------------------------------------------------------------------------------------------------- checks 1-5
def integrity():
    for rel, h in FROZEN.items():
        check(f"frozen file {rel}", sha(ROOT / rel) == h)
    for kit, zname in KITS.items():
        kdir = ROOT / "experiments" / kit
        with zipfile.ZipFile(ROOT / "archives/provenance" / zname) as z:
            members = {n.split("/", 1)[1]: n for n in z.namelist() if not n.endswith("/") and "/" in n}
            mism = [m for m, n in members.items() if not (kdir / m).is_file() or z.read(n) != (kdir / m).read_bytes()]
            extra = [str(p.relative_to(kdir)) for p in kdir.rglob("*") if p.is_file() and str(p.relative_to(kdir)) not in members
                     and "__pycache__" not in p.parts and p.suffix != ".pyc"]
        check(f"kit {kit} byte-identical to {zname}", not mism and not extra,
              f"{len(members)} files" if not mism and not extra else f"differs: {mism[:3]} extra: {extra[:3]}")
        sums = kdir / "KIT_SHA256SUMS.txt"
        if sums.exists():
            bad = [l for l in sums.read_text().splitlines() if l.strip() and sha(kdir / l.split(None, 1)[1].strip()) != l.split()[0]]
            check(f"kit {kit} own KIT_SHA256SUMS", not bad, f"{len(bad)} mismatches" if bad else "")
    lines = [l.split(None, 1) for l in (ROOT / "archives/ARCHIVES.sha256").read_text().splitlines() if l.strip()]
    bad = [p for h, p in lines if sha(ROOT / "archives" / p.strip()) != h]
    check(f"archive checksums ({len(lines)} files)", not bad, f"mismatch: {bad}" if bad else "")
    for rdir, zname in RESULTS.items():
        base = ROOT / "results" / rdir
        with zipfile.ZipFile(ROOT / "archives" / zname) as z:
            names = {n: n for n in z.namelist()}
            prefix = Path(zname).stem + "/"
            bad = 0; n = 0
            for f in base.rglob("*"):
                if f.is_file():
                    rel = str(f.relative_to(base)); member = names.get(rel) or names.get(prefix + rel)
                    n += 1; bad += member is None or z.read(member) != f.read_bytes()
        check(f"results/{rdir} identical to archive members", bad == 0 and n > 0, f"{n} files" + (f", {bad} differ" if bad else ""))
    osoc = ROOT / "results/0_original_soc"; kit = ROOT / "experiments/0_original_soc/round2_outputs"
    check("results/0_original_soc identical to kit v2 outputs",
          all((osoc / f).read_bytes() == (kit / f).read_bytes() for f in ("results_2x2.md", "paired_differences_by_seed.csv")))
    for kp, rp in PROTOCOLS:
        a = json.loads((ROOT / "experiments" / kp).read_text()); b = json.loads((ROOT / "results" / rp).read_text())
        check(f"protocol {Path(kp).name} identical to results", a == b)


# ------------------------------------------------------------------------------------------------------------- check 6
def cell_value(data, cell, seed, outcome):
    key = (cell["fleet_config"], cell["mass_config"], cell["algorithm"], float(cell["initial_soc"]), float(cell["alpha_energy"]), seed)
    r = data.get(key)
    if r is None or r.get(outcome, "") in ("", None):
        return None
    return float(r[outcome])


def recompute_ab(tag, run_level, protocol, contrasts):
    data = {}
    for r in rows(run_level):
        data[(r["fleet_config"], r["mass_config"], r["algorithm"], float(r["initial_soc"]), float(r["alpha_energy"]), r["seed"])] = r
    seeds = sorted({k[-1] for k in data})
    reported = {r["id"]: r for r in rows(contrasts)}
    bad = []; n_ok = 0
    for con in json.loads(Path(protocol).read_text())["contrasts"]:
        vals = []
        for s in seeds:
            tot = 0.0; ok = True
            for t in con["terms"]:
                if t.get("type") == "pctdiff":
                    a = cell_value(data, t["a"], s, t["outcome"]); b = cell_value(data, t["b"], s, t["outcome"])
                    if a is None or b in (None, 0): ok = False; break
                    tot += t["w"] * 100.0 * (a - b) / b
                else:
                    v = cell_value(data, t["cell"], s, con["outcome"])
                    if v is None: ok = False; break
                    tot += t["w"] * v
            if ok: vals.append(tot)
        rep = reported[con["id"]]
        if len(vals) < 2:
            bad += [] if rep["mean"] in ("nan", "") else [con["id"]]; continue
        n, m, lo, hi = summary(vals)
        if n == int(rep["n"]) and close(m, rep["mean"]) and close(lo, rep["ci_low"]) and close(hi, rep["ci_high"]):
            n_ok += 1
        else:
            bad.append(con["id"])
    check(f"{tag}: {n_ok + len(bad)} contrasts recomputed from run_level.csv (n, mean, 95% CI)", not bad, f"mismatch: {bad[:5]}" if bad else "")
    check_holm(tag, rows(contrasts), lambda r: r["family"], "p", "holm_p")


def recompute_c():
    rl = rows(ROOT / "results/C_dynamics/analysis/run_level.csv")
    ref = {(r["algorithm"], r["seed"], r["mode"]): float(r["battery_Wh"]) for r in rl if r["mode"] in ("off", "on")}
    se = rows(ROOT / "results/C_dynamics/analysis/seed_effects.csv")
    bad = sum(not close(100 * (ref[(r["algorithm"], r["seed"], "off")] - ref[(r["algorithm"], r["seed"], "on")])
                        / ref[(r["algorithm"], r["seed"], "off")], r["whole_pct"], 1e-6) for r in se)
    check(f"C: {len(se)} seed-level whole-run savings recomputed from reference runs", bad == 0, f"{bad} differ" if bad else "")
    bad = []
    for r in rows(ROOT / "results/C_dynamics/analysis/primary_contrasts.csv"):
        n, m, lo, hi = summary([float(x[r["estimand"]]) for x in se if x["algorithm"] == r["algorithm"]])
        if not (n == int(r["n"]) and close(m, r["mean"]) and close(lo, r["ci_low"]) and close(hi, r["ci_high"])):
            bad.append(f"{r['algorithm']}/{r['estimand']}")
    check("C: 6 primary contrasts recomputed from seed effects", not bad, f"mismatch {bad}" if bad else "")
    check_holm("C", rows(ROOT / "results/C_dynamics/analysis/primary_contrasts.csv"), lambda r: "primary")


def recompute_d():
    base = ROOT / "results/D_cost_proxy/analysis"
    R = {(r["seed"], r["mass"], r["algorithm"], r["arm"]): r for r in rows(base / "run_level.csv")}
    eff = rows(base / "paired_seed_effects.csv"); bad = 0
    for p in eff:
        a = R[(p["seed"], p["mass"], p["algorithm"], p["arm"])]; b = R[(p["seed"], p["mass"], p["algorithm"], p["reference"])]
        e0 = float(R[(p["seed"], p["mass"], p["algorithm"], "e0")]["battery_Wh"])
        exp = {"battery_pp": 100 * (float(b["battery_Wh"]) - float(a["battery_Wh"])) / e0,
               "wait_s": float(b["wait_s"]) - float(a["wait_s"]), "ride_s": float(b["ride_s"]) - float(a["ride_s"]),
               "completed": float(a["completed"]) - float(b["completed"])}
        bad += sum(not close(v, p[k], 1e-9) for k, v in exp.items())
    check(f"D: {len(eff)} paired seed effects recomputed from run_level.csv", bad == 0, f"{bad} values differ" if bad else "")
    groups = defaultdict(list)
    for p in eff:
        for k in ("battery_pp", "wait_s", "ride_s", "completed"):
            groups[(p["mass"], p["algorithm"], p["arm"], p["reference"], k)].append(float(p[k]))
    bad = []; prim = rows(base / "primary_contrasts.csv")
    for r in prim:
        n, m, lo, hi = summary(groups[(r["mass"], r["algorithm"], r["arm"], r["reference"], r["metric"])])
        if not (close(m, r["mean"]) and close(lo, r["ci_low"]) and close(hi, r["ci_high"])):
            bad.append(f"{r['family']}/{r['mass']}/{r['algorithm']}/{r['arm']}/{r['metric']}")
    check(f"D: {len(prim)} primary rows recomputed (mean, 95% CI)", not bad, f"mismatch {bad[:4]}" if bad else "")
    check_holm("D", prim, lambda r: r["family"])


def recompute_ef(tag, folder, factors):
    base = ROOT / "results" / folder / "analysis"
    rl = rows(base / "run_level.csv"); key = lambda r: tuple(r[f] for f in factors) + (r["algorithm"], r["seed"])
    on = {key(r): r for r in rl if r["alpha"] in ("1", "1.0")}; off = {key(r): r for r in rl if r["alpha"] in ("0", "0.0")}
    eff = rows(base / "paired_seed_effects.csv"); bad = 0
    pf = {"E": ("network", "window_s"), "F": ("config", "initial_soc")}[tag]
    for p in eff:
        k = tuple(p[f] for f in pf) + (p["algorithm"], p["seed"])
        if tag == "F":
            k = (p["config"], str(float(p["initial_soc"])), p["algorithm"], p["seed"])
            k = next(kk for kk in on if kk[0] == k[0] and float(kk[1]) == float(k[1]) and kk[2:] == k[2:])
        a, b = on[k], off[k]
        bad += not close(100 * (float(b["battery_Wh"]) - float(a["battery_Wh"])) / float(b["battery_Wh"]), p["battery_saving_pct"], 1e-9)
        bad += not close(float(a["ride_s"]) - float(b["ride_s"]), p["ride_s_on_minus_off"], 1e-9)
        bad += not close(float(a["completed"]) - float(b["completed"]), p["completed_on_minus_off"], 1e-9)
    check(f"{tag}: {len(eff)} paired seed effects recomputed from run_level.csv", bad == 0, f"{bad} values differ" if bad else "")
    sav = defaultdict(dict)
    for p in eff:
        lvl = (p[pf[0]], ("SOC " + str(int(round(100 * float(p["initial_soc"])))) + "%") if tag == "F" else p[pf[1]])
        sav[lvl + (p["algorithm"],)][p["seed"]] = float(p["battery_saving_pct"])
    prim = rows(base / "primary_contrasts.csv"); bad = []
    for r in prim:
        parts = [x.strip() for x in r["contrast"].split("/")]
        if r["family"] == "simple":
            if tag == "E":
                lvl = (parts[0], parts[1].replace(" s", "")); alg = parts[2]
            else:
                lvl = (parts[0], parts[1]); alg = parts[2]
            vals = list(sav[lvl + (alg,)].values())
        else:
            m = re.match(r"(.+) minus (.+)", parts[0]); x, y = m.group(1).strip(), m.group(2).strip(); fixed, alg = parts[1], parts[2]
            def lv(level):
                if tag == "E":
                    if level in ("UM", "UTP"):
                        return ("UM_district" if level == "UM" else "UTP", fixed.replace(" s", ""))
                    return (fixed, level)
                if level.endswith("%"):
                    return (fixed, "SOC " + level)
                return (level, fixed)
            A, B = sav[lv(x) + (alg,)], sav[lv(y) + (alg,)]
            vals = [A[s] - B[s] for s in sorted(A) if s in B]
        if not vals:
            bad.append(r["contrast"]); continue
        n, mm, lo, hi = summary(vals)
        if not (n == int(r["n"]) and close(mm, r["mean"]) and close(lo, r["ci_low"]) and close(hi, r["ci_high"])):
            bad.append(r["contrast"])
    check(f"{tag}: {len(prim)} simple and interaction contrasts recomputed (n, mean, 95% CI)", not bad, f"mismatch {bad[:4]}" if bad else "")
    check_holm(tag, prim, lambda r: r["family"])


def statistics_checks():
    recompute_ab("A", ROOT / "results/A_payload/run_level.csv", ROOT / "results/A_payload/experiment_A_payload.json",
                 ROOT / "results/A_payload/analysis/contrasts.csv")
    recompute_ab("B", ROOT / "results/B_fleet/run_level.csv", ROOT / "results/B_fleet/experiment_B_fleet.json",
                 ROOT / "results/B_fleet/analysis/contrasts.csv")
    recompute_c(); recompute_d()
    recompute_ef("E", "E_network", ("network", "window_s"))
    recompute_ef("F", "F_road_load", ("config", "initial_soc"))


# ---------------------------------------------------------------------------------------------------------- checks 7-8
def scripts():
    r = subprocess.run([sys.executable, str(ROOT / "verification/c_native_reference_check/compare_c_references.py")],
                       capture_output=True, text=True)
    check("C native reference check (16 runs identical)", r.returncode == 0, r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-200:])
    out = ROOT / "analysis/output"
    def numbers(path):   # every number in a CSV/JSON/MD output, in order (robust to last-digit library differences)
        return [float(x) for x in re.findall(r"-?\d+\.\d+(?:e[-+]?\d+)?|-?\d+(?:e[-+]?\d+)?", path.read_text())]
    names = ["synthesis_energy_by_study.csv", "synthesis_ride_by_study.csv", "synthesis_pooled.json"]
    before = {n: numbers(out / n) for n in names if (out / n).exists()}
    with tempfile.TemporaryDirectory() as tmp:      # regenerate elsewhere: verification never modifies the repository
        r = subprocess.run([sys.executable, str(ROOT / "analysis/synthesis.py"), "--out", tmp], capture_output=True, text=True)
        after = {n: numbers(Path(tmp) / n) for n in names if (Path(tmp) / n).exists()}
    same = r.returncode == 0 and len(before) == 3 and all(
        len(before[n]) == len(after[n]) and all(close(a, b, 1e-9) for a, b in zip(before[n], after[n])) for n in names)
    check("post hoc synthesis reproduces analysis/output (all values within 1e-9 relative)", same,
          "" if same else (r.stderr[-300:] or "outputs changed"))


def main():
    print(f"Repository: {ROOT}\n")
    integrity(); statistics_checks(); scripts()
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} checks passed." + (f" FAILED: {failed}" if failed else " ALL PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
