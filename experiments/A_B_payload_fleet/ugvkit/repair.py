"""Targeted repair of probe records (kit v3.1). The original campaign is opened read-only and never modified.

1. Finds every completed run whose probe energy accounting cannot pass with its original record: schema-1 (v3.0) probe
   files with unequal-cardinality rounds, or any record failing the v3.1 accounting. Unaffected runs are not rerun.
2. Re-executes ONLY those runs, from their unchanged run specs, with the v3.1 runner, into REPAIR_DIR/runs/<label>.
   Runs are resumable and failures are detected exactly as in bin/launch.py.
3. Verifies each repaired run against its original:
   * simulator outputs identical (timing columns excluded): run_summary, energy feasibility, request results, wait
     diagnostics, pool energy, vehicle results, assignment events, charging events, vehicle SOC snapshots;
   * canonical workload hash identical;
   * every schema-1 probe field identical (so the sdec_pct estimand is unchanged);
   * v3.1 accounting PASS (all-round planned energy = battery withdrawal within 0.5% and = assignment_events sum).
   Only runs that pass all of this are marked VERIFIED and used by validate/extract/analyze --repair.
4. Writes affected_runs.csv, repair_report.json/.md and DEVIATIONS_entry.md (text for protocols/DEVIATIONS.md).

usage: python bin/repair.py --protocol P.json --campaign ORIGINAL --repair-out NEW_FOLDER --repo REPO --python PY [--jobs N]
       python bin/repair.py ... --identify-only      (list affected runs, run nothing)
"""
import argparse, csv, fcntl, json, os, signal, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from . import FROZEN_APP_SHA256, __version__
from .common import expand_protocol, load_json, repo_paths, sha256_file, sha256_json, spec_hash, write_json
from .probe import LEGACY_FIELDS, accounting, events_energy
from . import launch as L

COMPARE_FILES = ["run_summary.csv", "energy_feasibility_summary.csv", "request_results.csv", "request_wait_diagnostics.csv",
                 "pool_energy_summary.csv", "vehicle_results.csv", "assignment_events.csv", "charging_events.csv",
                 "vehicle_soc_snapshots.csv"]
DROP = {"run_id", "assignment_runtime_ms", "dispatch_runtime_mean_ms", "dispatch_runtime_p95_ms", "dispatch_runtime_p99_ms",
        "dispatch_runtime_max_ms", "dispatch_budget_miss_count", "dispatch_budget_miss_percent", "trial_index"}

def rows(p):
    return [{k: v for k, v in r.items() if k not in DROP} for r in csv.DictReader(open(p))]

def results_dir(rd):
    return Path(rd) / load_json(Path(rd) / "RUN_OK.json")["results_dir"]

def identify(specs, camp):
    affected = []
    for sp in specs:
        rd = camp / "runs" / sp["label"]
        if not sp["probe"]["enabled"] or not (rd / "RUN_OK.json").exists() or not (rd / "probe_stats.json").exists():
            continue
        res = results_dir(rd); pr = load_json(rd / "probe_stats.json")
        bat = float(next(csv.DictReader(open(res / "run_summary.csv")))["total_battery_withdrawn_Wh"])
        evE, nev = events_energy(res); acc = accounting(pr, bat, evE)
        if acc["status"] != "PASS":
            affected.append({"label": sp["label"], "algorithm": sp["algorithm"], "fleet_config": sp["fleet_config"],
                             "initial_soc": sp["initial_soc"], "alpha_energy": sp["alpha_energy"], "seed": sp["seed"],
                             "reason": acc["status"], "probe_schema": acc["schema"],
                             "rounds_cardinality_differs": pr["rounds_cardinality_differs"],
                             "legacy_plan_energy_active_Wh": pr["plan_energy_active_Wh"], "battery_Wh": bat,
                             "assignment_events_energy_Wh": evE,
                             "legacy_gap_pct": 100.0 * (pr["plan_energy_active_Wh"] - bat) / bat,
                             "events_vs_battery_pct": 100.0 * (evE - bat) / bat, "spec": sp})
    return affected

def verify(spec, camp, rep):
    o = camp / "runs" / spec["label"]; r = rep / "runs" / spec["label"]
    if not (r / "RUN_OK.json").exists():
        return {"label": spec["label"], "status": "NOT_RUN", "problems": ["repaired run did not complete"]}
    ro, rr = results_dir(o), results_dir(r); problems = []
    for f in COMPARE_FILES:
        if (ro / f).exists() != (rr / f).exists():
            problems.append(f"{f}: present in only one run")
        elif (ro / f).exists() and rows(ro / f) != rows(rr / f):
            problems.append(f"{f}: differs")
    if (ro / "canonical_requests.sha256").read_text().split()[0] != (rr / "canonical_requests.sha256").read_text().split()[0]:
        problems.append("canonical workload hash differs")
    if sha256_file(rr / "backend_source.py") != FROZEN_APP_SHA256:
        problems.append("repaired run did not use the frozen simulator")
    po, pn = load_json(o / "probe_stats.json"), load_json(r / "probe_stats.json")
    for k in LEGACY_FIELDS:
        if po.get(k) != pn.get(k):
            problems.append(f"probe field {k}: original {po.get(k)} repaired {pn.get(k)}")
    bat = float(next(csv.DictReader(open(rr / "run_summary.csv")))["total_battery_withdrawn_Wh"])
    evE, _ = events_energy(rr); acc = accounting(pn, bat, evE)
    if acc["status"] != "PASS":
        problems.append("repaired accounting " + acc["status"] + ": " + "; ".join(acc["messages"]))
    s = next(csv.DictReader(open(ro / "run_summary.csv")))
    return {"label": spec["label"], "status": "VERIFIED" if not problems else "MISMATCH", "problems": problems,
            "algorithm": spec["algorithm"], "fleet_config": spec["fleet_config"], "initial_soc": spec["initial_soc"],
            "alpha_energy": spec["alpha_energy"], "seed": spec["seed"],
            "completed": int(s["completed_requests"]), "battery_Wh": bat,
            "rounds_cardinality_differs": pn["rounds_cardinality_differs"],
            "all_rounds_active_energy_Wh": pn.get("all_rounds_active_energy_Wh"),
            "compared_energy_Wh": pn["plan_energy_active_Wh"], "unequal_rounds_active_energy_Wh": pn.get("unequal_rounds_active_energy_Wh"),
            "compared_energy_share_pct": 100.0 * pn["plan_energy_active_Wh"] / pn["all_rounds_active_energy_Wh"] if pn.get("all_rounds_active_energy_Wh") else None,
            "accounting_gap_pct": 100.0 * (pn.get("all_rounds_active_energy_Wh", 0) - bat) / bat}

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--protocol", required=True); ap.add_argument("--campaign", required=True)
    ap.add_argument("--repair-out", required=True); ap.add_argument("--repo", required=False)
    ap.add_argument("--python", default=sys.executable); ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=3600); ap.add_argument("--max-retries", type=int, default=1)
    ap.add_argument("--identify-only", action="store_true")
    a = ap.parse_args(argv)
    protocol = load_json(a.protocol); specs = expand_protocol(protocol)
    camp = Path(a.campaign).expanduser().resolve(); rep = Path(a.repair_out).expanduser().resolve()
    if rep == camp or camp in rep.parents:
        raise SystemExit("The repair folder must be outside the original campaign folder.")
    affected = identify(specs, camp)
    print(f"{len(affected)} of {len(specs)} runs need a repaired probe record")
    for x in affected:
        print(f"  {x['label']}: {x['reason']}, {x['rounds_cardinality_differs']} unequal-cardinality rounds, "
              f"legacy gap {x['legacy_gap_pct']:+.3f}%, assignment events vs battery {x['events_vs_battery_pct']:+.2e}%")
    if a.identify_only:
        return 0
    if not a.repo:
        raise SystemExit("--repo is required to rerun the affected runs")
    app_src, graph_src, hot_src = repo_paths(a.repo)
    if sha256_file(app_src) != FROZEN_APP_SHA256:
        raise SystemExit("Repository app.py is not the frozen simulator.")
    marker = rep / ".ugvkit_repair.json"
    ident = {"repair_of_protocol": protocol["protocol_id"], "protocol_sha256": sha256_json(protocol), "original_campaign": str(camp)}
    if rep.exists() and any(rep.iterdir()):
        if not marker.exists():
            raise SystemExit(f"{rep} is not empty and is not a repair folder created by this kit.")
        m = load_json(marker)
        if any(m.get(k) != v for k, v in ident.items()):
            raise SystemExit(f"{rep} is a repair folder for a different protocol or campaign.")
    rep.mkdir(parents=True, exist_ok=True)
    lockf = open(rep / ".ugvkit.lock", "w")
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(f"Another process is using {rep}.")
    if not marker.exists():
        write_json(marker, {**ident, "kit_version": __version__, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    with open(rep / "affected_runs.csv", "w", newline="") as fh:
        cols = [k for k in affected[0].keys() if k != "spec"] if affected else ["label"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); [w.writerow(x) for x in affected]
    for x in affected:   # the repaired run must use exactly the original spec
        if spec_hash(x["spec"]) != load_json(camp / "runs" / x["label"] / "RUN_OK.json")["spec_hash"]:
            raise SystemExit(f"{x['label']}: protocol spec no longer matches the original run; refusing to repair")
    def _stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, signal.default_int_handler); signal.signal(signal.SIGTERM, _stop)
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = [ex.submit(L.run_one, x["spec"], rep, app_src, graph_src, hot_src, a.python, a.timeout, a.max_retries) for x in affected]
        try:
            for f in as_completed(futs):
                label, status, wall = f.result(); print(f"  rerun {status:8s} {wall:6.1f}s {label}", flush=True)
        except KeyboardInterrupt:
            L.STOP.set()
            for p in list(L.ACTIVE):
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            ex.shutdown(wait=True, cancel_futures=True)
            print("Interrupted; rerun the same command to resume the repair.", flush=True)
            return 130
    results = [verify(x["spec"], camp, rep) for x in affected]
    ok = sum(r["status"] == "VERIFIED" for r in results)
    report = {"kit_version": __version__, "protocol_id": protocol["protocol_id"], "original_campaign": str(camp),
              "runs_in_protocol": len(specs), "runs_affected": len(affected), "runs_verified": ok,
              "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "runs": results}
    write_json(rep / "repair_report.json", report)
    md = [f"# Probe repair: {protocol['protocol_id']}", "", f"Original campaign (read-only): `{camp}`", "",
          f"{len(affected)} of {len(specs)} runs needed a repaired probe record; {ok} VERIFIED.", "",
          "| Run | Policy | Config | SOC | alpha | Unequal rounds | Compared energy share | All-round vs battery | Status |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        share = f"{r['compared_energy_share_pct']:.2f}%" if r.get("compared_energy_share_pct") is not None else ""
        gap = f"{r['accounting_gap_pct']:+.2e}%" if r.get("accounting_gap_pct") is not None else ""
        md.append(f"| {r['label']} | {r.get('algorithm','')} | {r.get('fleet_config','')} | {r.get('initial_soc','')} | {r.get('alpha_energy','')} | "
                  f"{r.get('rounds_cardinality_differs','')} | {share} | {gap} | {r['status']}{(': ' + '; '.join(r['problems'])) if r['problems'] else ''} |")
    (rep / "repair_report.md").write_text("\n".join(md) + "\n")
    labels = ", ".join(r["label"] for r in results)
    (rep / "DEVIATIONS_entry.md").write_text(
        f"| {time.strftime('%Y-%m-%d')} | {protocol['protocol_id']} | Probe accounting correction (kit v3.1). {len(affected)} of {len(specs)} "
        f"runs had rounds in which the energy-term and time-only matchings assigned different numbers of requests; the v3.0 probe "
        f"excluded those rounds from plan_energy_active_Wh, so the validator's comparison with battery withdrawal failed. "
        f"These runs were re-executed from unchanged specs into `{rep}`; {ok} reproduced every simulator output, the workload hash "
        f"and every original probe field exactly, and pass the corrected accounting. Original records preserved unchanged. "
        f"| Validation compared a comparison-only sum with the run total | None: sdec_pct and all simulator outcomes are unchanged. "
        f"Affected runs: {labels} |\n")
    print(f"repair report: {rep / 'repair_report.md'}  ({ok}/{len(affected)} VERIFIED)")
    return 0 if ok == len(affected) else 1
