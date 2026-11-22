# Experiment D — physics-derived surrogate and energy-weight sweep (v5)

## Question and design

Does time plus a physically determined passenger-km penalty reproduce energy-aware dispatch, and what is the practical energy/service trade-off as the energy weight changes? This follows A/B (payload and scale) and C (impulse responses). It does not assume C established a positive amplification mechanism.

Full SOC, 12 vehicles, 100 requests, baseline 825 kg cart / 80 kg passenger and physically plausible 455.8 kg cart / 100 kg passenger; Greedy and Hungarian; 40 fresh paired seeds. Seven arms per cell: native alpha 0, 0.25, 0.5, 1, 2, 4; and passenger-km proxy at alpha 1 (`pk1`). 1,120 confirmation runs. Excluded pilot: 28 instrumented runs plus 8 native controls, 36 total. Neither dataset is reused from earlier experiments. The high-mass-ratio configuration is a modeling sensitivity, not empirical calibration. The source file is unmodified; the original solver and feasibility logic are retained. Full SOC isolates the objective; the experiment is not a new low-SOC resilience claim.

## Theory and scope

Cruise approximation on the frozen flat network at v=22/3.6 m/s: e0 (empty Wh/km) = 1000[(m0*g*Crr+0.5*rho*Cd*A*v²)/eta + Paux/v]/3600; e1 (Wh/passenger-km) = 1000*mp*g*Crr/(3600*eta). kappa=e0*v/1000 (Wh/s). The signed change in passenger-km is calculated for the remaining candidate and baseline plans from original predicted path lengths and passenger counts, including remaining return-to-depot plans. The common committed leg cancels. Let t=clipped incremental duration (seconds), E=clipped true incremental energy (Wh), p=signed incremental passenger-km. At fixed alpha=1, beta=1 and gamma=0:

* Native cost C = t/600 + E/100.
* Proxy P = t/600 + (kappa*t+e1*p)/100; equivalently a positive multiple of `t + lambda*p`, where lambda=(e1/100)/(1/600+kappa/100). No fitting and no clipping of signed proxy cost.
* Exact identity C=P+R/100, R=E-kappa*t-e1*p. R includes non-cruise motion, dwell and clipping effects; not presumed zero. Candidate residual summaries measure approximation errors; a distance-based residual is also reported.

Proposition (same feasible decision set): if x minimizes C and y minimizes P, then 0 <= C(y)-C(x) <= [R(y)-R(x)]/100 <= 2 max|R|/100. Proof: subtract the cost identity and use P(y)<=P(x), C(x)<=C(y). For Hungarian, use sums over complete matching actions of maximum cardinality (including each chosen insertion). For Greedy, only the insertion-level bound is guaranteed, since Greedy need not globally minimize a matching. Code verifies these bounds for each feasible pair and Hungarian round. This is a deterministic regret bound on the native *objective*, not a claim of equal actions, equal energy or whole-run equivalence. Native e1/proxy hypothetical decisions are re-solved on the same candidate state for all arms; descriptive summaries preselect native e1 trajectories. Unequal-cardinality rounds count toward disagreement but not local energy/time gaps. All executed assignment energy is recorded regardless of cardinality. Original battery-reserve feasibility still uses true predictor energy, not proxy approximation. No additional route feasibility or state mutation is introduced.

## Ubuntu commands (run from unzipped kit)

Use the same Python environment as Experiment C. The default frozen source repo is `~/ugv-benchmark-public`; override `--repo` if you used another. `--repo` must have `src/frozen/app.py`, `inputs/utp_graph.graphml` (or `.xml` fallback), `inputs/hotspot_locations.csv`. All three hashes must match the user-supplied source. The experiment never alters that repo. Default outputs are `~/ugv_v5_campaigns`, independent of older campaigns.

```bash
cd ~/energy_soc_experiment_kit_v5
sha256sum -c KIT_SHA256SUMS.txt --quiet && echo 'KIT INTACT'
PY=~/energy_soc_experiment_kit/kit/venv/bin/python
"$PY" tests/test_frozen_hooks.py ~/ugv-benchmark-public/src/frozen/app.py
df -h ~
"$PY" experiment_d.py run --pilot --jobs 2
```

Stop if any check fails. The pilot must print `PILOT PASS` and `EXPORT VERIFIED`. In particular the eight native-control runs must match instrumented native results in assignment event history and service/energy results. It is a manipulation/safety check only, not a basis for selecting successful arms. Share pilot output if any discrepancy arises. After successful pilot, preserve protocol hashes before starting confirmation:

```bash
sha256sum protocols/experiment_D.json protocols/pilot_D.json
"$PY" experiment_d.py run --jobs 2
```

Confirmation requires about 3.8 GiB free initially (conservative 3 MiB/run plus reserve) and roughly a few hours at two jobs, hardware-dependent. Resume interrupted runs by reissuing the identical command; invalid/incomplete attempts are quarantined, not deleted. Existing results are accepted only after per-run hash and accounting checks. A campaign identity locks the protocol, source/inputs, kit code, Python and package versions. A lock prevents concurrent launches in the same directory. Do not modify code or environment mid-campaign. To see progress from another terminal:

```bash
cd ~/energy_soc_experiment_kit_v5
~/energy_soc_experiment_kit/kit/venv/bin/python experiment_d.py status
```

Add `--pilot` to status to count pilot. Marker counts are provisional until validated. Full completion automatically validates, analyzes, builds figures, and verifies export checksums. If a validation or export issue occurs, rerun the identical command; validated runs are reused. To validate without launching missing runs, use `experiment_d.py validate` with identical options. Only upload the resulting confirmation ZIP from `~/ugv_v5_campaigns/experiment_D_equivalence/exports/` for review. Export has the protocol, identity, exact run matrix, report, per-seed comparisons, every run's metrics, round diagnostics and PDF/PNG plots, not multi-gigabyte raw logs. Keep the originals.

## Prespecified inference and reporting

Primary equivalence: pk1 vs native e1 within each mass/policy cell; paired TOST with Holm across 16 component tests, margins ±1 percentage point battery (denominator each seed's e0 battery), ±10 s pickup wait, ±10 s mean passenger time, ±1 completed request. All four adjusted tests must pass for a cell-level equivalence claim. 95% paired t intervals displayed; not simultaneous intervals. The other 24 primary comparisons measure battery savings versus e0 for each nonzero arm (including pk1), paired sign-flip with 100,000 Monte Carlo draws, Holm across family; no independently pooled dispatch rounds. Report all prespecified outcomes and failed equivalence tests. Secondary service and comparisons against e1 intervals are descriptive and unadjusted. Pareto plot uses cell mean battery and wait; `condition_means.csv`, `sweep_intervals.csv` include passenger time/completion and permit additional trade-off interpretation. No claim of optimal alpha or broad transport-model validity. Prospective registration of a second network or independent vehicle measurements remains separate.

## Test record

All three supplied source/input SHA-256 values verified. Local tests execute the exact frozen `_predict`, `pair_cost`, `stop_plan_masses`, cost function, Greedy/Hungarian and assignment validation with controlled synthetic legs/states, including a committed-leg fixture; 28 arm fixtures and 24 uninstrumented native comparisons pass. A separate artificial-data test processes the complete 36/1120-record pilot and confirmation, runs all 40 contrasts, builds figures, and verifies both exports. These are not full simulator runs. The local environment lacks graph/geospatial dependencies; the mandatory 36-run Ubuntu pilot is the real integration test. No confirmatory simulations were run during kit construction. Protocols, code and source identity are locked before confirmation.

For convenience `JOBS=2 bash run_D.sh pilot` and `JOBS=2 bash run_D.sh run` implement the commands above with the same defaults. `REPO`, `PY` and `OUT_ROOT` can override the defaults, consistently across pilot and confirmation. The descriptive pooling proxy `passenger_km_per_productive_km` is completed-passenger km divided by productive vehicle km, not an exact occupancy-time or pooling rate; incomplete passenger distances are excluded.
