"""Builds the prespecified protocol JSON files for Experiments A and B (and the smoke test).
Run once; the JSON files are the authoritative protocols. Changing them after confirmatory runs start is a deviation
and must be reported. usage: python build_protocols.py OUTPUT_DIR
"""
import json, sys
from pathlib import Path

FROZEN_APP_SHA256 = "7b52bb550414469937da3098f91313b366137d43bd48b8465b840a97bffeb0a0"
# Every seed already used anywhere in this project (never reused for confirmatory work).
EXCLUDED = (list(range(1001, 20002, 1000))        # original S1-S5 campaigns, ablation, SOC pilot
            + list(range(21001, 60002, 1000))     # 2x2 energy-weight x SOC confirmatory campaign
            + list(range(81001, 88002, 1000))     # arrival-surge probe
            + [91001, 92001, 93001, 94001, 99001]  # 2x2 pilot and smoke test
            + [901001, 902001, 903001]            # v3 manipulation check and smoke tests
            + list(range(905001, 911002, 1000)))  # kit self-tests
POLICIES = ["hungarian", "greedy"]

def cell(fc, mc, alg, soc, a):
    return {"fleet_config": fc, "mass_config": mc, "algorithm": alg, "initial_soc": soc, "alpha_energy": a}

def C(cid, family, outcome, unit, margin, prediction, terms, note=""):
    return {"id": cid, "family": family, "outcome": outcome, "unit": unit, "margin": margin,
            "prediction": prediction, "terms": terms, "note": note}

# ---------------- Experiment A: payload / load sensitivity ----------------
MASS = [
    {"id": "M825_P80", "overrides": {}, "rho_pct": 7.4, "physical": True,
     "basis": "Frozen baseline: GMTLSV six-seat enclosed cart, 825 kg incl. batteries; 80 kg per passenger."},
    {"id": "M587_P80", "overrides": {"UGV_EMPTY_MASS_KG": 586.5}, "rho_pct": 9.5, "physical": True,
     "basis": "Six-seat open electric cart class with lead-acid pack: Club Car Onward 6-passenger HP Electric, non-lifted, curb 1,293 lb (586.5 kg)."},
    {"id": "M456_P80", "overrides": {"UGV_EMPTY_MASS_KG": 455.8}, "rho_pct": 11.2, "physical": True,
     "basis": "Six-seat lithium cart class: Club Car Onward 6-passenger XR Lithium, non-lifted, curb 1,005 lb (455.8 kg)."},
    {"id": "M456_P100", "overrides": {"UGV_EMPTY_MASS_KG": 455.8, "UGV_PASSENGER_MASS_KG": 100.0}, "rho_pct": 14.0, "physical": True,
     "basis": "Same lithium cart; passengers carrying about 20 kg of luggage each. Full payload 600 kg, within the roughly 454-635 kg (1,000-1,400 lb) load range quoted for six-seat carts."},
    {"id": "M456_P160_STRESS", "overrides": {"UGV_EMPTY_MASS_KG": 455.8, "UGV_PASSENGER_MASS_KG": 160.0}, "rho_pct": 22.4, "physical": False,
     "basis": "NON-PHYSICAL model stress level (960 kg payload exceeds cart load ratings). Used only to test the functional form of the mechanism; never interpreted as an operating scenario."},
]
PHYS = [m for m in MASS if m["physical"]]
rbar = sum(m["rho_pct"] for m in PHYS) / len(PHYS)
den = sum((m["rho_pct"] - rbar) ** 2 for m in PHYS)
def slope_terms(outcome_alg, alpha=1, typ="cell", outcome=None):
    """OLS slope across the four physical levels per seed (units per percentage point of rho)."""
    t = []
    for m in PHYS:
        w = (m["rho_pct"] - rbar) / den
        if typ == "cell":
            t.append({"w": w, "cell": cell("V12R100", m["id"], outcome_alg, 1.0, alpha)})
        else:
            t.append({"w": w, "type": "pctdiff", "outcome": outcome, "a": cell("V12R100", m["id"], outcome_alg, 1.0, 1), "b": cell("V12R100", m["id"], outcome_alg, 1.0, 0)})
    return t

A_contrasts = []
for alg in POLICIES:
    A_contrasts += [
        C(f"A1_decision_saving_{alg}", "A_primary", "sdec_pct", "pp of run energy", 1.0, "positive (larger saving at higher rho), below the 1 pp margin",
          [{"w": 1, "cell": cell("V12R100", "M456_P100", alg, 1.0, 1)}, {"w": -1, "cell": cell("V12R100", "M825_P80", alg, 1.0, 1)}],
          "Decision-level saving of the energy-term choice versus the time-only choice in the same fleet state, alpha_E=1 trajectories; highest physical rho minus baseline."),
        C(f"A2_realized_saving_{alg}", "A_primary", "battery_Wh", "pp of run energy", 1.0, "negative (larger realized saving at higher rho), magnitude below 1 pp",
          [{"w": 1, "type": "pctdiff", "outcome": "battery_Wh", "a": cell("V12R100", "M456_P100", alg, 1.0, 1), "b": cell("V12R100", "M456_P100", alg, 1.0, 0)},
           {"w": -1, "type": "pctdiff", "outcome": "battery_Wh", "a": cell("V12R100", "M825_P80", alg, 1.0, 1), "b": cell("V12R100", "M825_P80", alg, 1.0, 0)}],
          "Realized run-level effect of alpha_E (percent change in battery withdrawal) at the highest physical rho minus at baseline. Negative = more saving."),
        C(f"A3_r_{alg}", "A_manipulation", "r_within", "correlation", None, "negative (energy and duration less collinear)",
          [{"w": 1, "cell": cell("V12R100", "M456_P100", alg, 1.0, 1)}, {"w": -1, "cell": cell("V12R100", "M825_P80", alg, 1.0, 1)}]),
        C(f"A4_insertion_change_{alg}", "A_manipulation", "insertion_change_pct", "pp of assigned requests", None, "positive",
          [{"w": 1, "cell": cell("V12R100", "M456_P100", alg, 1.0, 1)}, {"w": -1, "cell": cell("V12R100", "M825_P80", alg, 1.0, 1)}]),
        C(f"A5_decision_saving_slope_{alg}", "A_trend", "sdec_pct", "pp per pp of rho", None, "positive", slope_terms(alg)),
        C(f"A6_realized_saving_slope_{alg}", "A_trend", "battery_Wh", "pp per pp of rho", None, "negative", slope_terms(alg, typ="pct", outcome="battery_Wh")),
        C(f"A7_stress_decision_saving_{alg}", "A_stress_exploratory", "sdec_pct", "pp of run energy", 1.0, "positive",
          [{"w": 1, "cell": cell("V12R100", "M456_P160_STRESS", alg, 1.0, 1)}, {"w": -1, "cell": cell("V12R100", "M825_P80", alg, 1.0, 1)}]),
        C(f"A8_stress_realized_saving_{alg}", "A_stress_exploratory", "battery_Wh", "pp of run energy", 1.0, "negative",
          [{"w": 1, "type": "pctdiff", "outcome": "battery_Wh", "a": cell("V12R100", "M456_P160_STRESS", alg, 1.0, 1), "b": cell("V12R100", "M456_P160_STRESS", alg, 1.0, 0)},
           {"w": -1, "type": "pctdiff", "outcome": "battery_Wh", "a": cell("V12R100", "M825_P80", alg, 1.0, 1), "b": cell("V12R100", "M825_P80", alg, 1.0, 0)}]),
    ]
    for m in MASS:  # simple effects per level, descriptive
        A_contrasts.append(C(f"A9_realized_saving_{m['id']}_{alg}", "A_descriptive", "battery_Wh", "pp of run energy", None, "negative",
            [{"w": 1, "type": "pctdiff", "outcome": "battery_Wh", "a": cell("V12R100", m["id"], alg, 1.0, 1), "b": cell("V12R100", m["id"], alg, 1.0, 0)}]))
        A_contrasts.append(C(f"A9_decision_saving_{m['id']}_{alg}", "A_descriptive", "sdec_pct", "pp of run energy", None, "positive",
            [{"w": 1, "cell": cell("V12R100", m["id"], alg, 1.0, 1)}]))

A = {
    "protocol_id": "EXP_A_PAYLOAD", "version": "1.0", "status": "PRESPECIFIED: fixed before any confirmatory run",
    "title": "Payload (load-sensitivity) experiment: does a larger passenger-to-vehicle mass ratio make energy-aware dispatch matter?",
    "frozen_app_sha256": FROZEN_APP_SHA256, "excluded_seeds": EXCLUDED,
    "mechanism": ("Per km, cruise time is load-independent (163.6 s/km) while energy is a0 + a1*n (n passengers onboard). "
                  "An insertion's energy increment is therefore approximately a0*dD + a1*dPK + stop terms, and its duration increment dD/v + stop/dwell terms. "
                  "Only a1*dPK (added passenger-km) is not proportional to duration, so the lever is rho = a1/a0. Uniformly scaling all energy costs would only "
                  "re-weight alpha_E, which the energy-only probe showed cannot exceed about 2% saving. Payload changes rho, i.e. the non-proportional share."),
    "design": {
        "seeds": "601001:700001:1000",
        "fleet_configs": [{"id": "V12R100", "vehicles": 12, "requests": 100}],
        "mass_configs": [{"id": m["id"], "overrides": m["overrides"], "rho_pct": m["rho_pct"], "physical": m["physical"], "basis": m["basis"]} for m in MASS],
        "algorithms": POLICIES, "initial_soc": [1.0], "alpha_energy": [0, 1],
        "beta_time": 1.0, "soc_cost_weight": 0.0, "probe": True,
    },
    "hypotheses": {
        "H_A1_manipulation": "Within-request energy-duration correlation falls and the share of insertion decisions changed by alpha_E rises as rho increases (A3, A4, trend).",
        "H_A2_decision": "The decision-level saving of the energy term rises with rho (A1, A5). Predicted size from the 2-seed manipulation check on excluded seeds: about +0.4 pp from M825_P80 to M456_P100, i.e. below the 1 pp margin.",
        "H_A3_realized": "The realized run-level saving rises with rho (A2, A6). Prediction: any increase is smaller than the 1 pp margin, so energy weighting stays operationally negligible across physically plausible payloads.",
        "H_A4_stress": "At the non-physical stress level the decision-level saving exceeds the physical levels (A7), confirming the functional form. Exploratory.",
    },
    "outcomes": {
        "sdec_pct": "Decision-level saving (% of run withdrawal): 100*(planned dE of the time-only choice - planned dE of the energy-term choice)/battery_Wh, summed over dispatch rounds in the same fleet states (probe).",
        "battery_Wh": "Gross modeled battery withdrawal per run; contrasts use the percent change between alpha_E=1 and 0 within seed.",
        "r_within": "Pooled within-request correlation of candidate dE and dT in the run (simulator cost diagnostics).",
        "insertion_change_pct": "Share of assigned requests whose insertion order would differ under the other alpha_E in the same state (probe).",
        "secondary_descriptive": ["matching_change_pct", "completed_per100", "km", "wait_s", "wh_per_completion", "blocked_pairs"],
    },
    "analysis": {
        "unit": "workload seed (paired across all conditions)", "ci": "paired 95% Student t",
        "test": "two-sided sign-flip: exact for lattice-valued differences, otherwise Monte Carlo with 1,000,000 draws (seed 20261120)",
        "multiplicity": "Holm within each family; A_primary has 4 tests and is confirmatory; other families are secondary or exploratory as named",
        "margin_rule": "A 95% CI inside +/- margin is reported as 'no effect larger than the margin'; Holm p < 0.05 with CI outside the margin as 'effect exceeding the margin'; Holm p < 0.05 with CI inside as 'detectable but below the margin'; anything else as 'inconclusive'.",
        "effect_sizes": "mean paired contrast, 95% CI, SD, d_z",
    },
    "sample_size": ("n = 100 seeds (2,000 runs). Realized percent-change SDs from the 320-run campaign: 3.2% (Hungarian) and 4.1% (Greedy) at 100% SOC. "
                    "Assuming independent levels, contrast SDs are 4.6% and 5.8%, giving 95% CI half-widths of about 0.9 and 1.2 pp at n = 100, "
                    "and 80% power at Holm alpha 0.0125 for realized changes of about 1.5 and 1.9 pp. The decision-level saving has a per-run SD of about 0.43 pp "
                    "(median over physical levels; maximum 0.70) in 30 kit self-test runs on excluded seeds, so its contrast SD is about 0.6-1.0 pp: at n = 100 "
                    "A1 is estimated to about +/-0.12-0.20 pp and increases of 0.20-0.33 pp are detectable with 80% power. Realized increases smaller than "
                    "about 1.5-1.9 pp will be reported as estimates, not as detected effects."),
    "contrasts": A_contrasts,
    "deviations_policy": "Any change after the first confirmatory run is logged in DEVIATIONS.md with date and reason; results are reported under the original protocol as well.",
}

# ---------------- Experiment B: fleet size versus demand intensity ----------------
FC = [{"id": "V12R100", "vehicles": 12, "requests": 100, "note": "baseline S4; replicates the 2x2 on fresh seeds"},
      {"id": "V24R100", "vehicles": 24, "requests": 100, "note": "S3: fleet doubled, identical requests per seed (fleet-size effect at fixed demand)"},
      {"id": "V24R200", "vehicles": 24, "requests": 200, "note": "fleet and demand doubled: same 8.33 requests per vehicle as V12R100 (scale effect at fixed intensity)"}]
B_contrasts = []
def inter(fc, alg, outcome="completed_per100"):
    return [{"w": 1, "cell": cell(fc, "M825_P80", alg, 0.25, 1)}, {"w": -1, "cell": cell(fc, "M825_P80", alg, 0.25, 0)},
            {"w": -1, "cell": cell(fc, "M825_P80", alg, 1.0, 1)}, {"w": 1, "cell": cell(fc, "M825_P80", alg, 1.0, 0)}]
def socloss(fc, alg):
    return [{"w": 1, "cell": cell(fc, "M825_P80", alg, 0.25, 1)}, {"w": -1, "cell": cell(fc, "M825_P80", alg, 1.0, 1)}]
for alg in POLICIES:
    for fc in ("V24R100", "V24R200"):
        B_contrasts.append(C(f"B1_interaction_completions_{fc}_{alg}", "B_primary", "completed_per100", "completions per 100 requests", 1.0,
                             "within margin (no alpha_E x SOC interaction), replicating the 12-UGV result", inter(fc, alg)))
    B_contrasts.append(C(f"B2_interaction_completions_V12R100_{alg}", "B_replication", "completed_per100", "completions per 100 requests", 1.0,
                         "within margin (replication on fresh seeds)", inter("V12R100", alg)))
    B_contrasts.append(C(f"B3_socloss_fleetsize_{alg}", "B_service_scale", "completed_per100", "completions per 100 requests", 1.0,
                         "positive: doubling the fleet at fixed demand doubles the above-reserve energy, so the 25% SOC service loss shrinks",
                         socloss("V24R100", alg) + [{"w": -t["w"], "cell": t["cell"]} for t in socloss("V12R100", alg)]))
    B_contrasts.append(C(f"B4_socloss_scale_{alg}", "B_service_scale", "completed_per100", "completions per 100 requests", 1.0,
                         "two-sided, no directional prediction: same requests per vehicle, but a larger pooled fleet may rotate charging more easily",
                         socloss("V24R200", alg) + [{"w": -t["w"], "cell": t["cell"]} for t in socloss("V12R100", alg)]))
    for fc in ("V12R100", "V24R100", "V24R200"):
        B_contrasts.append(C(f"B5_realized_saving_{fc}_{alg}", "B_energy", "battery_Wh", "pp of run energy", 1.0, "negative, magnitude below 1 pp",
            [{"w": 1, "type": "pctdiff", "outcome": "battery_Wh", "a": cell(fc, "M825_P80", alg, 1.0, 1), "b": cell(fc, "M825_P80", alg, 1.0, 0)}]))
        B_contrasts.append(C(f"B6_decision_saving_{fc}_{alg}", "B_mechanism", "sdec_pct", "pp of run energy", None, "positive",
            [{"w": 1, "cell": cell(fc, "M825_P80", alg, 1.0, 1)}]))
        B_contrasts.append(C(f"B7_socloss_{fc}_{alg}", "B_descriptive", "completed_per100", "completions per 100 requests", None, "negative at V12R100",
            socloss(fc, alg)))
    B_contrasts.append(C(f"B8_decision_saving_fleetsize_{alg}", "B_mechanism", "sdec_pct", "pp of run energy", None,
                         "negative: with more idle vehicles fewer insertions are pooled, so the energy term has less to act on",
                         [{"w": 1, "cell": cell("V24R100", "M825_P80", alg, 1.0, 1)}, {"w": -1, "cell": cell("V12R100", "M825_P80", alg, 1.0, 1)}]))
B = {
    "protocol_id": "EXP_B_FLEET", "version": "1.0", "status": "PRESPECIFIED: fixed before any confirmatory run",
    "title": "Larger-fleet validation: do the 12-UGV findings hold with 24 UGVs, separating fleet size from demand intensity?",
    "frozen_app_sha256": FROZEN_APP_SHA256, "excluded_seeds": EXCLUDED,
    "demand_rationale": ("Keeping 100 requests isolates fleet size at fixed demand but halves requests per vehicle (8.33 to 4.17) and doubles above-reserve energy. "
                         "Doubling to 200 requests keeps requests per vehicle at 8.33 and isolates scale. Both are needed; with the same seed, V12R100 and "
                         "V24R100 receive identical request sets (workload depends only on seed and request count), so the fleet-size contrast is exactly matched."),
    "charging_note": "Charging rules unchanged: each idle vehicle at its home depot charges independently (1,500 W DC), no charger queue or site power cap. With 24 vehicles on three depots this is more optimistic than with 12; stated as a limitation.",
    "design": {"seeds": "701001:740001:1000", "fleet_configs": FC, "mass_configs": [{"id": "M825_P80", "overrides": {}}],
               "algorithms": POLICIES, "initial_soc": [1.0, 0.25], "alpha_energy": [0, 1],
               "beta_time": 1.0, "soc_cost_weight": 0.0, "probe": True},
    "hypotheses": {
        "H_B1": "No alpha_E x initial-SOC interaction on completions at 24 UGVs, for 100 or 200 requests (B1; CI within +/-1 per 100).",
        "H_B2": "The 25% SOC service loss shrinks when the fleet doubles at fixed demand (B3 positive), because above-reserve energy doubles.",
        "H_B3": "At fixed intensity (V24R200 vs V12R100) the service loss is compared two-sided (B4); no directional prediction.",
        "H_B4": "The energy term's realized and decision-level savings stay below 1 pp in every configuration (B5, B6); decision-level saving is smaller with 24 UGVs at fixed demand (B8).",
        "H_B5": "The 12-UGV 2x2 null replicates on fresh seeds (B2).",
    },
    "outcomes": {"completed_per100": "completed requests per 100 generated requests", "battery_Wh": "gross modeled withdrawal (percent change within seed)",
                 "sdec_pct": "decision-level saving, as in Experiment A",
                 "secondary_descriptive": ["blocked_pairs", "failures_all_blocked", "km", "wait_s", "wh_per_completion", "r_within", "insertion_change_pct", "charged_Wh"]},
    "analysis": A["analysis"] | {"multiplicity": "Holm within each family; B_primary (4 tests) is confirmatory; B_service_scale (4 tests) is a prespecified secondary family; others secondary/descriptive"},
    "sample_size": ("n = 40 seeds (960 runs). From the 320-run campaign: SD of the per-seed alpha x SOC interaction on completions 2.0-2.9 per 100, and SD of the 25% SOC service loss 2.3-2.5 per 100. "
                    "At n = 40 the 95% CI half-width is about 0.65-0.92 per 100 for the interaction and about 0.8 for the service-loss contrasts, "
                    "enough to place intervals inside the +/-1 margin when the true value is near 0, and to detect a service-loss change of 2 per 100 with power > 0.9 at Holm alpha 0.0125."),
    "contrasts": B_contrasts,
    "deviations_policy": A["deviations_policy"],
}

SMOKE = {
    "protocol_id": "SMOKE_V3", "version": "1.0", "status": "smoke test only; seeds excluded from all confirmatory analyses",
    "excluded_seeds": [],
    "design": {"seeds": [904001], "fleet_configs": FC, "mass_configs": [{"id": "M825_P80", "overrides": {}}],
               "algorithms": ["hungarian"], "initial_soc": [1.0, 0.25], "alpha_energy": [0, 1],
               "beta_time": 1.0, "soc_cost_weight": 0.0, "probe": True},
    "contrasts": [],
}
SMOKE_A = {
    "protocol_id": "SMOKE_V3_PAYLOAD", "version": "1.0", "status": "smoke test only; seeds excluded from all confirmatory analyses",
    "excluded_seeds": [],
    "design": {"seeds": [904001], "fleet_configs": [{"id": "V12R100", "vehicles": 12, "requests": 100}],
               "mass_configs": A["design"]["mass_configs"], "algorithms": ["hungarian"], "initial_soc": [1.0], "alpha_energy": [0, 1],
               "beta_time": 1.0, "soc_cost_weight": 0.0, "probe": True},
    "contrasts": [],
}
EXCLUDED_CHECK = set(EXCLUDED)
for p in (A, B):
    from_spec = p["design"]["seeds"].split(":")
    ss = range(int(from_spec[0]), int(from_spec[1]) + 1, int(from_spec[2]))
    assert not (set(ss) & EXCLUDED_CHECK), p["protocol_id"]
assert not set(range(601001, 700002, 1000)) & set(range(701001, 740002, 1000))
SMOKE["excluded_seeds"] = []; EXCLUDED.append(904001)  # smoke seed is excluded from confirmatory protocols
A["excluded_seeds"] = sorted(set(EXCLUDED)); B["excluded_seeds"] = sorted(set(EXCLUDED))

out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
for name, p in (("experiment_A_payload.json", A), ("experiment_B_fleet.json", B), ("smoke_fleet.json", SMOKE), ("smoke_payload.json", SMOKE_A)):
    (out / name).write_text(json.dumps(p, indent=2))
    print("wrote", out / name, "contrasts:", len(p["contrasts"]))
