"""Probe energy accounting shared by validate, extract and repair (kit v3.1).

Two different energy sums exist and must never be confused:
  * all-round active energy: planned increments of every assignment the run made. In this model it equals the run's
    battery withdrawal (observed agreement about 1e-10 relative) and the sum of predicted_incremental_route_energy_Wh
    in the simulator's own assignment_events.csv. This is what the accounting check compares with battery withdrawal.
  * comparison energy (plan_energy_active_Wh / plan_energy_alt_Wh): only rounds where both matchings assign the same
    number of pairs. This is the decision-level estimand (sdec_pct) and is intentionally NOT the run total.

Probe schema 1 (kit v3.0) recorded only the comparison energy. For a schema-1 run with no unequal-cardinality rounds the
comparison energy IS the all-round energy (no round was excluded). For a schema-1 run with unequal-cardinality rounds the
all-round energy was not recorded by the probe; such runs need a repaired probe record (bin/repair.py).
"""
import csv, json
from pathlib import Path

ENERGY_TOL = 0.005        # all-round planned vs battery withdrawal (unchanged from v3.0)
IDENTITY_RTOL = 1e-9      # internal sums and probe-vs-simulator-events (exact up to float summation order)
LEGACY_FIELDS = ["rounds", "rounds_matching_differs", "rounds_cardinality_differs", "selected_pairs", "selected_pairs_busy",
                 "pairs_changed", "insertion_changed", "plan_energy_active_Wh", "plan_energy_alt_Wh", "plan_time_active_s",
                 "plan_time_alt_s", "plan_rounds_compared", "alpha_alt"]

def events_energy(res_dir):
    """Sum of predicted incremental energy over the simulator's own assignment log (independent of the probe)."""
    rows = list(csv.DictReader(open(Path(res_dir) / "assignment_events.csv")))
    return sum(float(r["predicted_incremental_route_energy_Wh"]) for r in rows), len(rows)

def close(a, b, rtol=IDENTITY_RTOL, scale=None):
    return abs(a - b) <= rtol * max(1.0, abs(scale if scale is not None else max(abs(a), abs(b))))

def load_repair_index(repair_dir):
    """Labels whose repaired probe record was verified by bin/repair.py -> repaired run folder."""
    if not repair_dir:
        return {}
    rep = Path(repair_dir).expanduser().resolve()
    rpt = rep / "repair_report.json"
    if not rpt.exists():
        raise SystemExit(f"{rpt} not found: run bin/repair.py first")
    report = json.load(open(rpt))
    return {r["label"]: rep / "runs" / r["label"] for r in report["runs"] if r["status"] == "VERIFIED"}

def probe_record(rd, repair_index=None):
    """Return (probe dict, source) for a run folder, preferring a verified repaired record."""
    rd = Path(rd)
    if repair_index and rd.name in repair_index:
        return json.load(open(repair_index[rd.name] / "probe_stats.json")), "repair"
    return json.load(open(rd / "probe_stats.json")), "original"

def accounting(probe, battery_Wh, ev_energy_Wh):
    """Evaluate the probe's energy accounting. Returns dict with all_rounds_active_energy_Wh (or None), status and
    messages. Status: PASS, FAIL, or LEGACY_INCOMPLETE (schema-1 record that cannot be checked without repair)."""
    out = {"schema": int(probe.get("probe_schema_version", 1)), "messages": []}
    if out["schema"] >= 2:
        allE = probe["all_rounds_active_energy_Wh"]
        parts = probe["plan_energy_active_Wh"] + probe["unequal_rounds_active_energy_Wh"] + probe["rounds_without_alternative_active_energy_Wh"]
        if not close(allE, parts, scale=battery_Wh):
            out["messages"].append(f"internal: all-round {allE:.6f} != compared + unequal + no-alternative {parts:.6f}")
        if probe.get("rounds_without_alternative", 0) != 0:
            out["messages"].append(f"{probe['rounds_without_alternative']} rounds had assignments but no comparable alternative")
    else:
        if probe["rounds_cardinality_differs"] > 0:
            out.update(status="LEGACY_INCOMPLETE", all_rounds_active_energy_Wh=None,
                       messages=[f"schema-1 probe: {probe['rounds_cardinality_differs']} unequal-cardinality rounds were not "
                                 f"included in plan_energy_active_Wh; repaired probe record required"])
            return out
        allE = probe["plan_energy_active_Wh"]   # no round excluded: comparison sum equals the all-round sum
    out["all_rounds_active_energy_Wh"] = allE
    if battery_Wh > 0 and abs(allE - battery_Wh) / battery_Wh > ENERGY_TOL:
        out["messages"].append(f"all-round planned energy {allE:.2f} vs battery {battery_Wh:.2f} differ by more than 0.5%")
    if not close(allE, ev_energy_Wh, scale=battery_Wh):
        out["messages"].append(f"probe all-round energy {allE:.6f} != simulator assignment_events sum {ev_energy_Wh:.6f}")
    out["status"] = "FAIL" if out["messages"] else "PASS"
    return out

def campaign_has_legacy_probe(camp):
    """True if any finished run in the campaign carries a kit v3.0 (schema-1) probe record."""
    for f in (Path(camp) / "runs").glob("*/probe_stats.json"):
        try:
            if "probe_schema_version" not in json.loads(f.read_text()):
                return True
        except (OSError, ValueError):
            continue
    return False

def refuse_legacy_write(camp, repair, tool):
    """Kit v3.0 campaigns are read-only for v3.1 tools: their outputs belong in the repair folder."""
    if not repair and campaign_has_legacy_probe(camp):
        raise SystemExit(f"{camp} contains kit v3.0 probe records. To keep the original campaign unchanged, {tool} writes only to a "
                         f"repair folder: rerun with --repair <REPAIR_FOLDER> (see scripts/03_repair_experiment.sh).")
