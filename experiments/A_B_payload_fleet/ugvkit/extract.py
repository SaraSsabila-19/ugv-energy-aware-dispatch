"""Extract one tidy row per completed run (RUN_OK) into run_level.csv. Standard library only.

usage: python bin/extract.py --campaign OUT [--csv FILE] [--repair REPAIR_DIR]
With --repair, verified repaired probe records replace legacy ones and run_level.csv is written to the repair folder
(the original campaign folder is not modified). Simulator outputs are always read from the original runs.
sdec_pct (the decision-level estimand) is computed exactly as in v3.0: equal-cardinality rounds only, divided by battery
withdrawal. New columns report the all-round accounting and the unequal-cardinality rounds separately.
"""
import argparse, csv, json, math, os
from pathlib import Path
from .common import load_json
from .probe import accounting, events_energy, load_repair_index, probe_record

FIELDS = ["label", "protocol_id", "seed", "fleet_config", "vehicles", "requests", "mass_config", "algorithm",
          "initial_soc", "alpha_energy", "beta_time", "soc_cost_weight",
          "empty_mass_kg", "passenger_mass_kg", "arrival_window_s", "canonical_requests_sha256", "initial_fleet_sha256",
          "completed", "uncompleted", "completed_per100", "battery_Wh", "driving_Wh", "dwell_Wh", "parked_Wh", "grid_Wh", "charged_Wh",
          "km", "wait_s", "pickup_response_s", "wh_per_completion", "sim_duration_s", "blocked_pairs", "blocked_insertions",
          "failures", "failures_all_blocked", "passenger_km", "pooling_ratio", "mean_assignment_cost",
          "r_E_ss", "r_T_ss", "r_cross", "r_within",
          "probe_rounds", "matching_change_pct", "insertion_change_pct", "selected_pairs", "plan_E_active_Wh", "plan_E_alt_Wh",
          "plan_T_active_s", "plan_T_alt_s", "sdec_pct", "tdec_s", "plan_vs_battery_pct", "rounds_cardinality_differs",
          "probe_schema", "probe_source", "probe_accounting", "all_rounds_active_E_Wh", "events_E_Wh", "assignment_events",
          "unequal_active_E_Wh", "unequal_alt_E_Wh", "unequal_active_pairs", "unequal_alt_pairs", "compared_energy_share_pct",
          "dispatch_count", "dispatch_max_ms", "dispatch_over_300ms", "run_summary_sha256"]

def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")

def extract_run(rd, repair_index=None):
    rd = Path(rd); spec = load_json(rd / "run_spec.json"); ok = load_json(rd / "RUN_OK.json")
    res = rd / ok["results_dir"]; s = next(csv.DictReader(open(res / "run_summary.csv")))
    st = load_json(res / "run_settings.json"); par = st.get("parameters", {})
    ef = next(csv.DictReader(open(res / "energy_feasibility_summary.csv")))
    E = T = Cx = 0.0
    for x in csv.DictReader(open(res / "cost_diagnostics.csv")):
        try:
            if int(x["within_request_dof"] or 0) > 0 and float(x["within_request_energy_ss"]) > 0 and float(x["within_request_time_ss"]) > 0:
                E += float(x["within_request_energy_ss"]); T += float(x["within_request_time_ss"]); Cx += float(x["within_request_cross_sum"])
        except ValueError:
            pass
    rr = list(csv.DictReader(open(res / "request_results.csv")))
    wd = {x["request_id"]: x for x in csv.DictReader(open(res / "request_wait_diagnostics.csv"))}
    fails = [x for x in rr if x["request_completed"] != "1"]
    all_blocked = sum(1 for x in fails if wd.get(x["request_id"], {}).get("had_feasible_pair") == "0"
                      and wd.get(x["request_id"], {}).get("had_energy_blocked_pair") == "1")
    pkm = sum(f(x["passenger_distance_km"]) for x in rr if x["request_completed"] == "1" and x["passenger_distance_km"])
    snap = list(csv.DictReader(open(res / "vehicle_soc_snapshots.csv")))
    t0 = snap[0]["tick"] if snap else None
    fleet = sorted((x["vehicle_id"], x["home_depot_id"], x["initial_SOC_Wh"]) for x in snap if x["tick"] == t0)
    import hashlib
    fleet_sha = hashlib.sha256(json.dumps(fleet).encode()).hexdigest()
    bat = f(s["total_battery_withdrawn_Wh"]); km = f(s["total_distance_km"]); done = int(s["completed_requests"])
    row = {k: spec.get(k) for k in ("label", "protocol_id", "seed", "fleet_config", "vehicles", "requests", "mass_config",
                                     "algorithm", "initial_soc", "alpha_energy", "beta_time", "soc_cost_weight")}
    row.update(empty_mass_kg=par.get("UGV_EMPTY_MASS_KG"), passenger_mass_kg=par.get("UGV_PASSENGER_MASS_KG"),
               arrival_window_s=par.get("ARRIVAL_WINDOW_S"),
               canonical_requests_sha256=ok["canonical_requests_sha256"], initial_fleet_sha256=fleet_sha,
               completed=done, uncompleted=int(s["uncompleted_requests"]), completed_per100=100.0 * done / int(s["spawned_requests"]),
               battery_Wh=bat, driving_Wh=f(s["driving_Wh"]), dwell_Wh=f(s["dwell_Wh"]), parked_Wh=f(s["battery_parked_Wh"]),
               grid_Wh=f(s["total_grid_import_Wh"]), charged_Wh=f(s["total_energy_charged_Wh"]), km=km,
               wait_s=f(s["mean_deadline_limited_pickup_wait_s"]), pickup_response_s=f(s["mean_pickup_response_picked_up_s"]),
               wh_per_completion=bat / done if done else float("nan"), sim_duration_s=f(s["simulation_duration_s"]),
               blocked_pairs=int(ef["energy_blocked_pair_evaluations"]), blocked_insertions=int(ef["energy_blocked_insertions"]),
               failures=len(fails), failures_all_blocked=all_blocked, passenger_km=pkm,
               pooling_ratio=pkm / km if km else float("nan"), mean_assignment_cost=f(s["mean_assignment_cost"]),
               r_E_ss=E, r_T_ss=T, r_cross=Cx, r_within=Cx / math.sqrt(E * T) if E > 0 and T > 0 else float("nan"),
               dispatch_count=int(s["dispatch_count"]), dispatch_max_ms=f(s["dispatch_runtime_max_ms"]),
               dispatch_over_300ms=int(s["dispatch_budget_miss_count"]), run_summary_sha256=ok["run_summary_sha256"])
    pf = rd / "probe_stats.json"
    if pf.exists():
        p, source = probe_record(rd, repair_index); a = float(spec["alpha_energy"])
        z, zi = (0.0, 0) if p.get("rounds_cardinality_differs", 1) == 0 else ("", "")
        evE, nev = events_energy(res); acc = accounting(p, bat, evE); allE = acc.get("all_rounds_active_energy_Wh")
        row.update(probe_schema=acc["schema"], probe_source=source, probe_accounting=acc["status"],
                   all_rounds_active_E_Wh=allE if allE is not None else "", events_E_Wh=evE, assignment_events=nev,
                   # a schema-1 record without unequal-cardinality rounds has, by construction, zero unequal-round energy
                   unequal_active_E_Wh=p.get("unequal_rounds_active_energy_Wh", z), unequal_alt_E_Wh=p.get("unequal_rounds_alt_energy_Wh", z),
                   unequal_active_pairs=p.get("unequal_rounds_active_pairs", zi), unequal_alt_pairs=p.get("unequal_rounds_alt_pairs", zi),
                   compared_energy_share_pct=100.0 * p["plan_energy_active_Wh"] / allE if allE else "")
        # Saving of the energy-term choice relative to the time-only choice in the same state:
        # alpha=1 run: alt is the time-only choice; alpha=0 run: alt is the energy-term choice.
        if a == 1:
            sdec = 100.0 * (p["plan_energy_alt_Wh"] - p["plan_energy_active_Wh"]) / bat
            tdec = p["plan_time_active_s"] - p["plan_time_alt_s"]
        else:
            sdec = 100.0 * (p["plan_energy_active_Wh"] - p["plan_energy_alt_Wh"]) / bat
            tdec = p["plan_time_alt_s"] - p["plan_time_active_s"]
        row.update(probe_rounds=p["rounds"], matching_change_pct=100.0 * p["rounds_matching_differs"] / max(1, p["rounds"]),
                   insertion_change_pct=100.0 * p["insertion_changed"] / max(1, p["selected_pairs"]), selected_pairs=p["selected_pairs"],
                   plan_E_active_Wh=p["plan_energy_active_Wh"], plan_E_alt_Wh=p["plan_energy_alt_Wh"],
                   plan_T_active_s=p["plan_time_active_s"], plan_T_alt_s=p["plan_time_alt_s"], sdec_pct=sdec, tdec_s=tdec,
                   plan_vs_battery_pct=100.0 * (allE - bat) / bat if allE is not None else "",
                   rounds_cardinality_differs=p["rounds_cardinality_differs"])
    return row

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--campaign", required=True); ap.add_argument("--csv", default=None)
    ap.add_argument("--repair", default=None)
    a = ap.parse_args(argv)
    from .probe import refuse_legacy_write
    refuse_legacy_write(Path(a.campaign).expanduser().resolve(), a.repair, 'extract')
    camp = Path(a.campaign).expanduser().resolve(); repair_index = load_repair_index(a.repair)
    base = Path(a.repair).expanduser().resolve() if a.repair else camp
    out = Path(a.csv) if a.csv else base / "run_level.csv"
    rows = []; skipped = 0
    for rd in sorted((camp / "runs").glob("*")):
        if (rd / "RUN_OK.json").exists():
            rows.append(extract_run(rd, repair_index))
        else:
            skipped += 1
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    leg = sum(1 for r in rows if r.get("probe_accounting") == "LEGACY_INCOMPLETE")
    print(f"wrote {out}: {len(rows)} completed runs ({skipped} folders without RUN_OK skipped)"
          + (f"; {leg} legacy probe records lack all-round accounting (repair them)" if leg else ""))
    return 0
