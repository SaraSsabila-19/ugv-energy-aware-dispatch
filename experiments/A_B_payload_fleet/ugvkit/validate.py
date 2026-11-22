"""Validate a campaign against its protocol. Exit code 1 if any check fails.

Checks (each listed in validation_report.json / .md):
  completeness   every expected run has RUN_OK.json with the matching spec hash; reports missing and failed runs
  source         every archived backend_source.py and run-folder app.py hash to the frozen FIX-19 identity
  overrides      recorded overrides equal the protocol's, and run_settings.json parameters show the overridden values
  settings       alpha_E, beta_T, gamma_SOC, cost mode, references, fleet size, request count as specified
  workload       one canonical request hash per (seed, request count) across ALL conditions (fleet, mass, policy, SOC, alpha);
                 distinct hashes across seeds
  fleet          identical initial fleet (vehicle, depot, initial Wh) within (seed, fleet config, SOC); initial Wh = 9000*SOC
  accounting     completed + uncompleted = requests
  probe          probe statistics present when enabled. v3.1 accounting (ugvkit/probe.py): the ALL-ROUND planned energy of the
                 assignments made equals battery withdrawal within 0.5% AND equals the simulator's own assignment_events
                 sum within 1e-9 relative; schema-2 records must also add up internally. Schema-1 (v3.0) records with
                 unequal-cardinality rounds cannot be checked and FAIL unless a verified repaired record is supplied
                 with --repair (bin/repair.py). The comparison energy behind sdec_pct is never compared with the run total.
  coverage       (information) runs and rounds where the two matchings assigned different numbers of pairs
  cost_change    switching alpha_E on raises the mean assignment cost (per seed, policy, configuration at 100% SOC)
  blocking       no energy blocking at 100% SOC (warning only); some blocking at 25% SOC under both alpha values
usage: python bin/validate.py --protocol P.json --campaign OUT [--repair REPAIR_DIR]
"""
import argparse, csv, collections, json
from pathlib import Path
from . import FROZEN_APP_SHA256
from .common import expand_protocol, load_json, sha256_file, spec_hash, write_json
from .probe import accounting, events_energy, load_repair_index, probe_record, campaign_has_legacy_probe

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--protocol", required=True); ap.add_argument("--campaign", required=True)
    ap.add_argument("--allow-incomplete", action="store_true", help="validate what exists (for partial or smoke campaigns)")
    ap.add_argument("--repair", default=None, help="repair folder from bin/repair.py; its VERIFIED probe records replace legacy ones")
    a = ap.parse_args(argv)
    protocol = load_json(a.protocol); specs = expand_protocol(protocol); camp = Path(a.campaign).expanduser().resolve()
    checks = collections.OrderedDict((k, {"status": "PASS", "details": []}) for k in
        ("completeness", "source", "overrides", "settings", "workload", "fleet", "accounting", "probe", "repair", "cost_change", "blocking", "coverage"))
    repair_index = load_repair_index(a.repair)
    if not a.repair:
        checks.pop("repair")
    cov = {"runs_with_unequal_rounds": 0, "unequal_rounds": 0, "legacy_incomplete": [], "repaired_used": 0}
    def fail(k, msg, warn=False):
        c = checks[k]
        if not warn: c["status"] = "FAIL"
        elif c["status"] == "PASS": c["status"] = "WARN"
        if len(c["details"]) < 50: c["details"].append(msg)
    if a.repair:
        # Re-verify every repaired run against its original now; the status stored in repair_report.json is not trusted.
        from .repair import verify
        rpt = load_json(Path(a.repair).expanduser().resolve() / "repair_report.json")
        if rpt.get("protocol_id") != protocol["protocol_id"] or Path(rpt.get("original_campaign", "")).resolve() != camp:
            fail("repair", f"repair report is for {rpt.get('protocol_id')} / {rpt.get('original_campaign')}, not this protocol and campaign")
            repair_index = {}
        by_label = {sp["label"]: sp for sp in specs}
        for r in rpt.get("runs", []):
            if r["status"] != "VERIFIED":
                fail("repair", f"{r['label']}: repair status {r['status']}: {'; '.join(r.get('problems', []))}")
        for label in list(repair_index):
            if label not in by_label:
                fail("repair", f"{label}: repaired run is not in this protocol"); repair_index.pop(label); continue
            v = verify(by_label[label], camp, Path(a.repair).expanduser().resolve())
            if v["status"] != "VERIFIED":
                fail("repair", f"{label}: re-verification {v['status']}: {'; '.join(v['problems'][:3])}"); repair_index.pop(label)
        if checks["repair"]["status"] == "PASS":
            checks["repair"]["details"].append(f"{len(repair_index)} repaired runs re-verified against their originals")
    rows = []; missing = []; failed = []
    for sp in specs:
        rd = camp / "runs" / sp["label"]
        if not (rd / "RUN_OK.json").exists():
            (failed if (rd / "RUN_FAILED.json").exists() else missing).append(sp["label"]); continue
        ok = load_json(rd / "RUN_OK.json")
        if ok.get("spec_hash") != spec_hash(sp):
            fail("completeness", f"{sp['label']}: RUN_OK spec hash differs from protocol"); continue
        res = rd / ok["results_dir"]
        if sha256_file(res / "backend_source.py") != FROZEN_APP_SHA256 or sha256_file(rd / "app.py") != FROZEN_APP_SHA256:
            fail("source", f"{sp['label']}: simulator hash mismatch")
        prov = load_json(rd / "overrides_and_provenance.json"); st = load_json(res / "run_settings.json"); par = st.get("parameters", {})
        rec = {k: v["run_value"] for k, v in prov.get("overrides", {}).items()}
        if rec != {k: float(v) for k, v in sp["overrides"].items()}:
            fail("overrides", f"{sp['label']}: recorded overrides {rec} != protocol {sp['overrides']}")
        for k, v in sp["overrides"].items():
            if k in par and abs(float(par[k]) - float(v)) > 1e-9:
                fail("overrides", f"{sp['label']}: run_settings {k}={par[k]} != {v}")
        s = next(csv.DictReader(open(res / "run_summary.csv")))
        want = {"alpha_energy": sp["alpha_energy"], "beta_time": sp["beta_time"], "soc_cost_weight": sp["soc_cost_weight"],
                "energy_reference_Wh": 100.0, "time_reference_s": 600.0, "fleet_size": sp["vehicles"], "spawned_requests": sp["requests"],
                "initial_soc_low": sp["initial_soc"], "initial_soc_high": sp["initial_soc"]}
        for k, v in want.items():
            if abs(float(s[k]) - float(v)) > 1e-9:
                fail("settings", f"{sp['label']}: {k}={s[k]} expected {v}")
        if s["cost_mode"] != "normalized" or s["depot_ids"] != "P02;P08;P16":
            fail("settings", f"{sp['label']}: cost mode/depots {s['cost_mode']} {s['depot_ids']}")
        if int(s["completed_requests"]) + int(s["uncompleted_requests"]) != sp["requests"]:
            fail("accounting", f"{sp['label']}: completed+uncompleted != requests")
        snap = list(csv.DictReader(open(res / "vehicle_soc_snapshots.csv"))); t0 = snap[0]["tick"]
        fleet = tuple(sorted((x["vehicle_id"], x["home_depot_id"], x["initial_SOC_Wh"]) for x in snap if x["tick"] == t0))
        if len(fleet) != sp["vehicles"] or any(abs(float(v[2]) - 9000.0 * sp["initial_soc"]) > 1e-6 for v in fleet):
            fail("fleet", f"{sp['label']}: initial fleet size or SOC wrong")
        ef = next(csv.DictReader(open(res / "energy_feasibility_summary.csv")))
        pr = None
        if sp["probe"]["enabled"]:
            if not (rd / "probe_stats.json").exists():
                fail("probe", f"{sp['label']}: probe_stats.json missing")
            else:
                pr, src = probe_record(rd, repair_index)
                cov["repaired_used"] += src == "repair"
                if abs(float(pr["alpha_alt"]) - float(sp["probe"]["alpha_alt"])) > 1e-12:
                    fail("probe", f"{sp['label']}: probe alternative alpha wrong")
                bat = float(s["total_battery_withdrawn_Wh"])
                evE, _ = events_energy(res)
                acc = accounting(pr, bat, evE)
                if pr["rounds_cardinality_differs"] > 0:
                    cov["runs_with_unequal_rounds"] += 1; cov["unequal_rounds"] += pr["rounds_cardinality_differs"]
                if acc["status"] == "LEGACY_INCOMPLETE":
                    cov["legacy_incomplete"].append(sp["label"])
                    fail("probe", f"{sp['label']} ({src}): " + "; ".join(acc["messages"]))
                elif acc["status"] == "FAIL":
                    fail("probe", f"{sp['label']} ({src}): " + "; ".join(acc["messages"]))
        rows.append(dict(spec=sp, wl=open(res / "canonical_requests.sha256").read().split()[0], fleet=fleet,
                         cost=float(s["mean_assignment_cost"]), blocked=int(ef["energy_blocked_pair_evaluations"])))
    if missing or failed:
        msg = f"{len(missing)} missing, {len(failed)} failed (of {len(specs)})"
        fail("completeness", msg, warn=a.allow_incomplete)
        for l in failed[:20]: checks["completeness"]["details"].append("FAILED " + l)
        for l in missing[:20]: checks["completeness"]["details"].append("missing " + l)
    wl = collections.defaultdict(set); seedwl = collections.defaultdict(set)
    for r in rows:
        wl[(r["spec"]["seed"], r["spec"]["requests"])].add(r["wl"]); seedwl[r["wl"]].add(r["spec"]["seed"])
    for k, v in wl.items():
        if len(v) != 1: fail("workload", f"seed {k[0]} requests {k[1]}: {len(v)} different workloads across conditions")
    for h, ss in seedwl.items():
        if len(ss) > 1: fail("workload", f"workload {h[:12]} shared by seeds {sorted(ss)}")
    fl = collections.defaultdict(set)
    for r in rows:
        fl[(r["spec"]["seed"], r["spec"]["fleet_config"], r["spec"]["initial_soc"])].add(r["fleet"])
    for k, v in fl.items():
        if len(v) != 1: fail("fleet", f"{k}: {len(v)} different initial fleets")
    cc = collections.defaultdict(dict)
    for r in rows:
        sp = r["spec"]
        if sp["initial_soc"] == 1.0:
            cc[(sp["seed"], sp["fleet_config"], sp["mass_config"], sp["algorithm"])][sp["alpha_energy"]] = r["cost"]
            if r["blocked"] != 0: fail("blocking", f"{sp['label']}: {r['blocked']} blocked pairs at 100% SOC", warn=True)
    for k, v in cc.items():
        if 0 in v and 1 in v and not v[1] > v[0]:
            fail("cost_change", f"{k}: mean assignment cost did not rise with alpha_E")
    low = collections.defaultdict(int)
    for r in rows:
        if r["spec"]["initial_soc"] < 1.0: low[r["spec"]["alpha_energy"]] += r["blocked"]
    for al, b in low.items():
        if b == 0: fail("blocking", f"alpha_E={al} at low SOC: reserve rule never blocked a pair")
    if cov["runs_with_unequal_rounds"] or cov["repaired_used"]:
        checks["coverage"]["status"] = "INFO"
        checks["coverage"]["details"].append(
            f"{cov['runs_with_unequal_rounds']} runs had {cov['unequal_rounds']} unequal-cardinality rounds (excluded from the "
            f"decision-level comparison by definition); {len(cov['legacy_incomplete'])} legacy records need repair; "
            f"{cov['repaired_used']} verified repaired probe records used")
    report = {"protocol_id": protocol["protocol_id"], "runs_expected": len(specs), "runs_validated": len(rows),
              "repair_dir": str(a.repair) if a.repair else None, "coverage": cov,
              "missing": len(missing), "failed": len(failed), "checks": checks,
              "overall": "FAIL" if any(c["status"] == "FAIL" for c in checks.values()) else "PASS"}
    if cov["legacy_incomplete"]:
        print(f"{len(cov['legacy_incomplete'])} runs have schema-1 probe records with unequal-cardinality rounds. Repair them with:\n"
              f"  python bin/repair.py --protocol {a.protocol} --campaign {camp} --repair-out <NEW_FOLDER> --repo <REPO> --python <PY>")
    lines = [f"# Validation: {protocol['protocol_id']}", "", f"Runs expected {len(specs)}, validated {len(rows)}, missing {len(missing)}, failed {len(failed)}."
             + (f" Repair folder: {a.repair}." if a.repair else ""), "",
             "| Check | Status | Details |", "| --- | --- | --- |"]
    for k, c in checks.items():
        lines.append(f"| {k} | {c['status']} | {'; '.join(c['details'][:3])} |")
    lines.append(f"\nOverall: **{report['overall']}**")
    # With --repair the merged-view report goes to the repair folder; the original campaign folder is left untouched.
    dest = Path(a.repair).expanduser().resolve() if a.repair else camp
    if not a.repair and campaign_has_legacy_probe(camp):
        # A kit v3.0 campaign is read-only for v3.1: print the report, write nothing into the original folder.
        print("\n".join(lines)); print("(kit v3.0 campaign: report printed only; nothing written to the original folder)")
        return 0 if report["overall"] == "PASS" else 1
    write_json(dest / "validation_report.json", report)
    (dest / "validation_report.md").write_text("\n".join(lines))
    print(f"report: {dest / 'validation_report.md'}")
    print("\n".join(lines))
    return 0 if report["overall"] == "PASS" else 1
