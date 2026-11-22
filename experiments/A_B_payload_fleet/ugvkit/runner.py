"""Execute ONE simulation inside its own run directory, using the frozen app.py copied there unchanged.

What happens in memory (never on disk):
  * the run's workload seed is appended to app.TRIAL_SEEDS (trial index = its position in that list);
  * whitelisted module constants are overridden (payload masses, arrival window), with old and new values recorded;
  * a non-built-in fleet/demand combination is registered in app.EXPERIMENT_CONFIG under a new scenario name;
  * optionally, a decision-sensitivity probe re-costs every vehicle-request pair under the alternative energy
    weight in the same fleet state, re-solves the matrix with the same algorithm and records whether the matching
    or the insertion order would differ, plus the planned energy/time of both choices. The probe restores every
    diagnostic counter the extra evaluation touches, so the run's own outputs are identical to an uninstrumented run.

usage: python runner.py --run-dir RUN_DIR      (RUN_DIR holds run_spec.json, app.py and the two input files)
"""
import argparse, json, math, os, sys, hashlib, platform, time

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--run-dir", required=True); a = ap.parse_args()
    rd = os.path.abspath(a.run_dir)
    spec = json.load(open(os.path.join(rd, "run_spec.json")))
    os.chdir(rd); sys.path.insert(0, rd)
    for k, v in spec["env"].items():
        if os.environ.get(k) != v:
            raise SystemExit(f"Environment variable {k} must be {v!r} before Python starts (launcher sets it).")
    if sys.flags.ignore_environment or sys.flags.hash_randomization:
        raise SystemExit("Run without -E/-I and with PYTHONHASHSEED=0 so hashing matches the published campaigns.")
    import numpy as np
    import app

    record = {"spec_label": spec["label"], "app_sha256": sha(os.path.join(rd, "app.py")),
              "inputs_sha256": {f: sha(os.path.join(rd, f)) for f in ("utp_graph.graphml", "hotspot_locations.csv")},
              "python": sys.version, "platform": platform.platform(), "overrides": {}, "scenario": None,
              "trial_seed": spec["seed"], "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    # Seed: append once; trial index is its position.
    if spec["seed"] not in app.TRIAL_SEEDS:
        app.TRIAL_SEEDS.append(spec["seed"])
    trial_index = app.TRIAL_SEEDS.index(spec["seed"])
    record["trial_index"] = trial_index

    # Whitelisted constant overrides.
    allowed = {"UGV_EMPTY_MASS_KG", "UGV_PASSENGER_MASS_KG", "UGV_MASS_KG", "ARRIVAL_WINDOW_S"}
    for name, value in spec["overrides"].items():
        if name not in allowed or not hasattr(app, name):
            raise SystemExit(f"Override not allowed or unknown: {name}")
        record["overrides"][name] = {"frozen_value": getattr(app, name), "run_value": float(value)}
        setattr(app, name, float(value))

    # Scenario: reuse a built-in name when the fleet/demand pair matches one, otherwise register a new one.
    known = {(12, 100): "S4", (24, 100): "S3", (12, 30): "S1", (18, 50): "S2"}
    key = (int(spec["vehicles"]), int(spec["requests"]))
    if key in known:
        scenario = known[key]
        cfg = app.EXPERIMENT_CONFIG[scenario]
        assert (cfg["vehicles"], cfg["requests"]) == key, "built-in scenario changed"
    else:
        scenario = f"V{key[0]}R{key[1]}"
        app.EXPERIMENT_CONFIG[scenario] = {"vehicles": key[0], "requests": key[1], "initial_soc_range": [1.0, 1.0]}
    record["scenario"] = scenario

    probe = None
    if spec["probe"]["enabled"]:
        probe = install_probe(app, np, float(spec["probe"]["alpha_alt"]))

    c = spec["cli"]; soc = spec["initial_soc"]
    sys.argv = ["app.py", "--headless", "--scenario", scenario, "--algorithm", spec["algorithm"],
                "--trial-index", str(trial_index), "--max-sim-s", str(c["max_sim_s"]),
                "--flush-every", str(c["flush_every"]), "--depot-layout", c["depot_layout"],
                "--dispatch-window-s", str(c["dispatch_window_s"]), "--dispatch-urgent-slack-s", str(c["dispatch_urgent_slack_s"]),
                "--initial-soc-range", str(soc), str(soc), "--alpha-energy", str(spec["alpha_energy"]),
                "--beta-time", str(spec["beta_time"]), "--soc-cost-weight", str(spec["soc_cost_weight"]),
                "--cost-mode", c["cost_mode"], "--energy-reference-wh", str(c["energy_reference_wh"]),
                "--time-reference-s", str(c["time_reference_s"])]
    record["argv"] = sys.argv[1:]
    json.dump(record, open("overrides_and_provenance.json", "w"), indent=2, sort_keys=True)
    rc = app.headless_main()
    if probe is not None:
        json.dump(probe.result(), open("probe_stats.json", "w"), indent=2)
    record["exit_code"] = rc
    record["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(record, open("overrides_and_provenance.json", "w"), indent=2, sort_keys=True)
    raise SystemExit(rc)


class Probe:
    def __init__(self):
        self.ALT, self.META = [], []
        # Schema 2 (kit v3.1). Fields from schema 1 keep their exact meaning:
        #   plan_energy_active_Wh / plan_energy_alt_Wh / plan_time_*_s / plan_rounds_compared are summed ONLY over
        #   rounds in which both matchings assign the same number of pairs (the decision-level comparison, i.e. the
        #   estimand of sdec_pct). They are NOT the run's total planned energy.
        # New in schema 2:
        #   all_rounds_active_energy_Wh / all_rounds_active_time_s: planned increments of every assignment the run
        #     actually made (all dispatch rounds); equals battery withdrawal in this model.
        #   unequal_rounds_*: the same quantities for rounds excluded from the comparison because the two matchings
        #     assign different numbers of pairs (possible for Greedy; impossible for Hungarian).
        #   rounds_without_alternative: rounds with assignments but no comparable alternative matrix (expected 0).
        self.s = dict(probe_schema_version=2, rounds=0, rounds_matching_differs=0, rounds_cardinality_differs=0,
                      selected_pairs=0, selected_pairs_busy=0, pairs_changed=0, insertion_changed=0,
                      plan_energy_active_Wh=0.0, plan_energy_alt_Wh=0.0, plan_time_active_s=0.0, plan_time_alt_s=0.0,
                      plan_rounds_compared=0,
                      all_rounds_active_energy_Wh=0.0, all_rounds_active_time_s=0.0, all_rounds_selected_pairs=0,
                      unequal_rounds_active_energy_Wh=0.0, unequal_rounds_alt_energy_Wh=0.0,
                      unequal_rounds_active_time_s=0.0, unequal_rounds_alt_time_s=0.0,
                      unequal_rounds_active_pairs=0, unequal_rounds_alt_pairs=0,
                      rounds_without_alternative=0, rounds_without_alternative_active_energy_Wh=0.0)
    def result(self):
        out = dict(self.s)
        out["alpha_alt"] = self.alpha_alt
        return out


def install_probe(app, np, alpha_alt):
    P = Probe(); P.alpha_alt = alpha_alt
    Engine = app.SharedRideEngine
    orig = Engine.pair_cost

    def patched(self, m, request, alpha, beta):
        # Snapshot every diagnostic the extra evaluation could change, evaluate the alternative, restore.
        nums = {k: v for k, v in vars(self).items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        sets = {k: set(v) for k, v in vars(self).items() if isinstance(v, set)}
        wds = self.wait_diagnostic_stats
        had = request.id in wds
        wcopy = dict(wds[request.id]) if had else None
        c_alt, meta_alt = orig(self, m, request, alpha_alt, beta)
        for k, v in nums.items():
            setattr(self, k, v)
        for k, v in sets.items():
            cur = getattr(self, k); cur.clear(); cur.update(v)
        if had:
            wds[request.id].clear(); wds[request.id].update(wcopy)
        else:
            wds.pop(request.id, None)
        c, meta = orig(self, m, request, alpha, beta)
        P.ALT.append(c_alt)
        P.META.append((meta, meta_alt, len(getattr(m, "planned_stops", None) or [])))
        return c, meta

    Engine.pair_cost = patched

    def wrap(fn):
        def inner(C, *a, **k):
            C = np.asarray(C, float)
            n = C.size
            alt = np.array(P.ALT[-n:], float).reshape(C.shape) if len(P.ALT) >= n else None
            metas = P.META[-n:] if len(P.META) >= n else None
            P.ALT.clear(); P.META.clear()
            pairs = fn(C, *a, **k)
            s = P.s
            if metas is not None:
                for (i, j) in set(map(tuple, pairs)):
                    mt = metas[i * C.shape[1] + j][0]
                    s["all_rounds_active_energy_Wh"] += mt["delta_energy"]; s["all_rounds_active_time_s"] += mt["delta_time"]
                    s["all_rounds_selected_pairs"] += 1
            if alt is None or metas is None or not np.isfinite(alt).any():
                if len(pairs):
                    s["rounds_without_alternative"] += 1
                    if metas is not None:
                        s["rounds_without_alternative_active_energy_Wh"] += sum(
                            metas[i * C.shape[1] + j][0]["delta_energy"] for i, j in set(map(tuple, pairs)))
                return pairs
            alt_pairs = fn(alt)  # Hungarian and Greedy are deterministic and stateless
            s["rounds"] += 1
            s1 = set(map(tuple, pairs))
            for (i, j) in s1:
                mt, ma, nst = metas[i * C.shape[1] + j]
                s["selected_pairs"] += 1
                if nst > 0: s["selected_pairs_busy"] += 1
                if mt is not None and ma is not None and mt["stops"] != ma["stops"]:
                    s["insertion_changed"] += 1
            if alt_pairs is not None:
                s2 = set(map(tuple, alt_pairs))
                if s1 != s2: s["rounds_matching_differs"] += 1
                s["pairs_changed"] += len(s1 - s2)
                if len(s1) != len(s2):
                    s["rounds_cardinality_differs"] += 1
                    s["unequal_rounds_active_energy_Wh"] += sum(metas[i * C.shape[1] + j][0]["delta_energy"] for i, j in s1)
                    s["unequal_rounds_alt_energy_Wh"] += sum(metas[i * C.shape[1] + j][1]["delta_energy"] for i, j in s2)
                    s["unequal_rounds_active_time_s"] += sum(metas[i * C.shape[1] + j][0]["delta_time"] for i, j in s1)
                    s["unequal_rounds_alt_time_s"] += sum(metas[i * C.shape[1] + j][1]["delta_time"] for i, j in s2)
                    s["unequal_rounds_active_pairs"] += len(s1); s["unequal_rounds_alt_pairs"] += len(s2)
                else:
                    ea = sum(metas[i * C.shape[1] + j][0]["delta_energy"] for i, j in s1)
                    eb = sum(metas[i * C.shape[1] + j][1]["delta_energy"] for i, j in s2)
                    ta = sum(metas[i * C.shape[1] + j][0]["delta_time"] for i, j in s1)
                    tb = sum(metas[i * C.shape[1] + j][1]["delta_time"] for i, j in s2)
                    s["plan_energy_active_Wh"] += ea; s["plan_energy_alt_Wh"] += eb
                    s["plan_time_active_s"] += ta; s["plan_time_alt_s"] += tb
                    s["plan_rounds_compared"] += 1
            return pairs
        inner.__name__ = fn.__name__
        return inner

    # Only deterministic, stateless solvers are re-solved; Random/Annealing use the run RNG and Round-Robin keeps a pointer.
    for key in ("hungarian", "greedy"):
        if key in app.ALGO_FUNCS:
            app.ALGO_FUNCS[key] = wrap(app.ALGO_FUNCS[key])
    return P


if __name__ == "__main__":
    main()
