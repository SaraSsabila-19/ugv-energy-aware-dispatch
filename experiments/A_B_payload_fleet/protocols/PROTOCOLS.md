# Prespecified protocols: Experiments A and B

The JSON files in this folder are authoritative: `experiment_A_payload.json` and `experiment_B_fleet.json`, built by `build_protocols.py`. This document explains them.

**Freeze before running.** Before the first confirmatory run, record the protocol hashes and keep that file with your records:

```
sha256sum experiment_A_payload.json experiment_B_fleet.json > PROTOCOL_SHA256SUMS.txt
```

Any later change is a deviation and goes in `DEVIATIONS.md`.

## What was known before these protocols were written

- **2×2 energy weight × initial SOC experiment (40 seeds, 21001–60001):**
  - The interaction was null at 12 UGVs / 100 requests.
  - Within-request energy–duration correlation r = 0.9973.
  - αE changed 6.2% of matchings and 8.6% of insertion orders.
  - Realized savings were 0.5–1.0%.
- **Physics** (frozen motion model, `tests`-independent calculation):
  - Cruise time is 163.6 s/km whatever the load.
  - Energy is a0 + a1·n per km, where n is passengers onboard. For the frozen vehicle, a0 = 39.34 Wh/km and a1 = 2.907 Wh/km per passenger.
  - So an insertion's energy increment ≈ a0·ΔD + a1·ΔPK + stop terms, and its duration increment ≈ ΔD/v + stop and dwell terms.
  - Only a1·ΔPK (added passenger-km) is not proportional to duration. The lever is therefore ρ = a1/a0, not payload as such.
  - Uniformly scaling every energy cost would only re-weight αE. The energy-only probe showed that cannot save more than about 2%.
- **Manipulation check** (Hungarian, 100% SOC, 2 excluded seeds 901001–902001):

  | Level | ρ | r | Decision-level saving |
  | --- | --- | --- | --- |
  | Baseline | 7.4% | 0.997 | 0.39% |
  | 587 kg | 9.5% | 0.995 | 0.57% |
  | 456 kg | 11.2% | 0.993 | 0.76% |
  | Non-physical stress | 22.4% | 0.966 | 2.25% |

  These values informed the predictions below. They are not used in any confirmatory analysis.

## Experiment A: payload / load sensitivity (`EXP_A_PAYLOAD`)

**Question.** Does a larger passenger-to-vehicle energy ratio make energy-aware dispatch matter? Within physically plausible payloads, how large can its effect become?

**Design.**
- 12 UGVs, 100 requests (S4 setting), 100% initial SOC.
- Hungarian and Greedy; αE ∈ {0, 1}; βT = 1; γSOC = 0.
- Decision-sensitivity probe on every run.
- 100 fresh seeds, 601001–700001 (step 1000).
- 5 mass levels × 2 αE × 2 policies × 100 = **2,000 runs**.

100% SOC isolates the cost mechanism. At 25% SOC, lighter vehicles would also have more range, which confounds feasibility with cost.

| Level | Empty mass | Passenger mass | ρ | Physical basis |
| --- | --- | --- | --- | --- |
| M825_P80 | 825 kg | 80 kg | 7.4% | Frozen GMTLSV enclosed six-seat cart |
| M587_P80 | 586.5 kg | 80 kg | 9.5% | Club Car Onward 6-passenger HP Electric (lead-acid), non-lifted curb mass |
| M456_P80 | 455.8 kg | 80 kg | 11.2% | Club Car Onward 6-passenger XR Lithium, non-lifted curb mass |
| M456_P100 | 455.8 kg | 100 kg | 14.0% | Same cart; passengers with about 20 kg luggage. 600 kg full payload, within six-seat cart load ratings |
| M456_P160_STRESS | 455.8 kg | 160 kg | 22.4% | **Non-physical** (960 kg payload); tests the functional form only |

Overrides are applied in memory to `UGV_EMPTY_MASS_KG`, `UGV_MASS_KG` (an alias copied at import) and `UGV_PASSENGER_MASS_KG`. They reach both prediction and execution, because the engine reads them at run time. Each run records them in `overrides_and_provenance.json` and `run_settings.json`.

**Hypotheses and predictions (stated before confirmatory runs).**

- **H_A1, manipulation.** r falls and the insertion-change rate rises from M825_P80 to M456_P100 (A3, A4; slopes in A_trend).
- **H_A2, decision-level.** The energy term's decision-level saving rises with ρ (A1, A5).
  - Predicted increase: about +0.4 pp, below the 1 pp margin.
- **H_A3, realized.** The realized saving rises with ρ (A2, A6).
  - Predicted: any increase smaller than 1 pp, so the effect stays operationally negligible across plausible payloads.
- **H_A4, exploratory.** At the stress level the decision-level saving exceeds every physical level (A7).

**Outcomes.**
- `sdec_pct`: decision-level saving, defined in the probe section below.
- `battery_Wh`: realized; contrasts use the within-seed percent change, αE = 1 vs 0.
- `r_within`, `insertion_change_pct` and `matching_change_pct`: manipulation checks.
- Descriptive: completions, km, deadline-limited wait, Wh per completion, energy-blocked pairs (expected 0 at 100% SOC).

**Families.**
- **A_primary** (confirmatory, Holm over 4): A1 and A2 for Hungarian and Greedy; the M456_P100 minus M825_P80 contrast.
- **A_manipulation:** Holm over 4.
- **A_trend:** OLS slope across the four physical levels per seed; Holm over 4.
- **A_stress_exploratory:** Holm over 4.
- **A_descriptive:** per-level simple effects; no inference claims.

**Margin.** 1.0 percentage point of run energy (about 60 Wh/run, 5 Wh/vehicle, 15 s of depot charging at baseline). Below this, energy weighting is treated as operationally negligible for this fleet.

**Sample size.** n = 100 is set by the realized outcome, the noisy one.
- From the 320-run campaign, per-seed SDs of the percent effect at 100% SOC are 3.23 pp (Hungarian) and 4.09 pp (Greedy).
- A contrast between two independent levels has SD 4.57 and 5.78 pp.
- At n = 100: 95% CI half-widths 0.91 and 1.15 pp.
- Detectable change at 80% power and Holm α = 0.0125: 1.53 and 1.93 pp.
- The decision-level outcome has a per-run SD of about 0.43 pp (median; maximum 0.70) in 30 self-test runs on excluded seeds. Its contrast SD is about 0.6–1.0 pp, so at n = 100, A1 is estimated to about ±0.12–0.20 pp, and increases of 0.20–0.33 pp are detectable at 80% power.
- An earlier 2-seed figure of 0.06 pp understated this spread; the self-test corrected it before any confirmatory run.
- Realized changes smaller than about 1.5–1.9 pp will therefore be reported as estimates with intervals, not as detected or excluded effects.
- `bin/sample_size.py --existing <your campaign>` reproduces these numbers.

## Experiment B: fleet size versus demand intensity (`EXP_B_FLEET`)

**Question.** Do the 12-UGV findings hold with 24 UGVs? Is any change due to fleet size or to demand intensity?

**Design.**
- Configurations:
  - V12R100: S4, the baseline; this also replicates the 2×2 on fresh seeds.
  - V24R100: S3, same requests as V12R100 for each seed.
  - V24R200: same 8.33 requests per vehicle as V12R100.
- Hungarian and Greedy; 100% and 25% SOC; αE ∈ {0, 1}; probe on.
- 40 fresh seeds, 701001–740001.
- 3 × 2 × 2 × 2 × 40 = **960 runs**.

**Why both 100 and 200 requests.**
- Keeping 100 requests isolates fleet size at fixed demand. But it also halves requests per vehicle and doubles above-reserve energy (24 × 450 Wh against 12 × 450 Wh).
- Doubling to 200 requests holds intensity fixed and isolates scale. Only the pair separates the two effects.
- Workloads depend only on seed and request count, so V12R100 and V24R100 receive identical request sets and the fleet-size contrast is exactly matched.

**Charging.** Unchanged: independent 1,500 W DC charging at each vehicle's home depot, no queue or site power cap. This is more optimistic with 24 vehicles on three depots; report it as a limitation.

**Hypotheses.**
- **H_B1, confirmatory:** no αE × SOC interaction on completions at V24R100 and V24R200 for either policy (B1; 95% CI within ±1 per 100).
- **H_B2:** the 25% SOC service loss shrinks when the fleet doubles at fixed demand (B3 positive).
- **H_B3:** at fixed intensity (V24R200 vs V12R100) the service-loss difference is tested two-sided (B4); no directional prediction.
- **H_B4:** realized and decision-level savings stay below 1 pp in every configuration (B5, B6). The decision-level saving is smaller at V24R100 than at V12R100 (B8), because more idle vehicles mean fewer pooled insertions for the energy term to act on.
- **H_B5:** the 12-UGV null replicates on fresh seeds (B2).

**Families.**
- **B_primary** (confirmatory, Holm over 4): B1.
- **B_service_scale** (prespecified secondary, Holm over 4): B3 and B4.
- B_replication, B_energy, B_mechanism and B_descriptive are secondary.

**Sample size.** From the 320-run campaign:
- Interaction SD is 2.01 (Hungarian) and 2.85 (Greedy) completions per 100; 25% SOC loss SD is 2.28 and 2.53.
- At n = 40, interaction half-widths are 0.64 and 0.91, and loss-contrast half-widths are 0.73 and 0.81.
- A service-loss change of 1.2–1.3 per 100 is detectable at 80% power and Holm α = 0.0125.

## Shared analysis rules

- **Unit and matching.** The workload seed is the unit, and every contrast is paired within seed. Seeds missing a cell are dropped and counted.
- **Tests and intervals.**
  - Two-sided sign-flip test: exact for lattice-valued differences (completions), otherwise Monte Carlo with 1,000,000 draws and RNG seed 20261120.
  - Paired 95% Student t intervals; d_z.
- **Verdicts:**
  - Holm p < 0.05 and the CI beyond the margin: "effect exceeding margin".
  - Holm p < 0.05 and the CI inside the margin: "detectable but below margin".
  - CI inside ±margin: "no effect larger than margin" (two one-sided tests at 2.5% per side).
  - Otherwise: "inconclusive".
- **Reporting.** Every prespecified contrast is reported, whatever its result. Exploratory and descriptive families are labelled as such.

## The decision-level probe

At every dispatch round, the probe also costs each vehicle–request pair under the other αE, in the same fleet state, and re-solves the matrix with the same algorithm.

It records:
- whether the matching would differ;
- for each assigned request, whether the chosen insertion order would differ;
- the planned energy and time increments of both choices.

The probe snapshots and restores every diagnostic counter that the extra evaluation touches. Kit tests show that runs with the probe are identical to runs without it, including all energy-blocking diagnostics.

The decision-level saving is computed per run over the rounds in which both matchings assign the same number of requests. Rounds where they differ can occur only for Greedy, because Hungarian maximises cardinality first and feasibility does not depend on αE. They are excluded because energy totals of different numbers of assignments are not comparable. This was the behaviour of the v3.0 code used for Experiment B and is retained unchanged; kit v3.1 only adds separate records of the excluded rounds and of the all-round total (see `DEVIATIONS.md`, 2026-11-21).

```
sdec = 100 × (ΣΔE of time-only choices − ΣΔE of energy-term choices) / battery withdrawal
```

The all-round sum of planned increments of the chosen insertions (`all_rounds_active_energy_Wh`, kit v3.1) equals the run's battery withdrawal to within about 10⁻⁸ %, and the simulator's own `assignment_events.csv` sum to within 10⁻⁹ relative. This shows the probe reads the plans that were executed. The comparison sums behind sdec (`plan_energy_active_Wh`, `plan_energy_alt_Wh`) equal the run total only when no round was excluded.

## Seeds used anywhere in the project (never reused for confirmatory work)

| Seeds | Use |
| --- | --- |
| 1001–20001 | Original campaigns |
| 21001–60001 | 2×2 confirmatory |
| 81001–88001 | Surge probe |
| 91001–94001, 99001 | 2×2 pilot and smoke test |
| 901001–904001 | v3 manipulation check and smoke tests |
| 905001–911001 | Kit self-tests |
| 30001, 45001 | Reused only by the regression test, which compares with existing runs and is not an experiment |
| **601001–700001** | **Experiment A** |
| **701001–740001** | **Experiment B** |
