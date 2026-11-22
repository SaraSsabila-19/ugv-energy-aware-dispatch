# energy_soc_experiment_kit_v3.1

Prespecified Experiments A (payload / load sensitivity) and B (fleet size versus demand intensity) for the UGV energy-aware assignment benchmark. The frozen FIX-19 simulator `app.py` (SHA-256 `7b52bb55…0a0`) is copied unchanged into every run folder. Seeds, payload masses, the arrival window and new fleet/demand combinations are set in memory and recorded per run.

**Kit v3.1 (2026-11-21)** corrects the probe energy accounting. If Experiment B was run with kit v3.0, follow `REPAIR_V3.1.md`: it reruns only the affected runs, in a separate folder, and revalidates all 960. Run Experiment A with this version. The simulator, protocols, seeds and estimands are unchanged (`protocols/DEVIATIONS.md`, 2026-11-21).

Contents:

- `protocols/`: prespecified protocols (`experiment_A_payload.json`, `experiment_B_fleet.json`), their builder, `PROTOCOLS.md`, `DEVIATIONS.md`
- `ugvkit/`: runner (in-run wrapper and probe), launcher, validator, extractor, analysis, figures, archive, regression, sample size
- `bin/`: command-line entry points
- `scripts/`: `config.sh` (paths), `00_check_environment.sh`, `01_smoke_and_regression.sh`, `02_run_experiment.sh A|B`, `03_repair_experiment.sh A|B` (v3.0 probe repair)
- `tests/`: self-test of failure detection and resume, the regression protocol, reference smoke values from the kit author's machine
- `COMPUTE.md`: time and disk estimates
- `TESTED.md`: exactly what was tested before delivery, and what was not
- `bin/physics.py`: recomputes the payload mechanism (energy and time per km versus load) with the frozen motion functions
- `tests/MANIPULATION_CHECK.md`: the exploratory check that informed Experiment A's predictions
- `REPAIR_V3.1.md`: the v3.1 correction and exact repair commands for a campaign run with kit v3.0
- `KIT_SHA256SUMS.txt`: checksums of every kit file

## 1. Unpack and set paths (Ubuntu)

```bash
cd ~/Downloads
unzip energy_soc_experiment_kit_v3.1.zip -d ~/
cd ~/energy_soc_experiment_kit_v3.1
sha256sum -c KIT_SHA256SUMS.txt --quiet && echo "kit intact"
```

The defaults in `scripts/config.sh` match your machine:

```bash
REPO=/home/sara/ugv-benchmark-public
PY=/home/sara/energy_soc_experiment_kit/kit/venv/bin/python
EXISTING=/home/sara/energy_soc_campaign_runs    # read-only; never written to
OUT_ROOT=$HOME/ugv_v3_campaigns                 # all new results go here
JOBS=(number of cores - 1)
```

Override any of them per command, for example `JOBS=6 OUT_ROOT=/data/v3 bash scripts/02_run_experiment.sh B`. The scripts refuse to run if `OUT_ROOT` is your existing campaign folder. The launcher also refuses to write into any non-empty folder it did not create.

## 2. Check the environment (changes nothing)

```bash
bash scripts/00_check_environment.sh
```

If matplotlib or scikit-learn is reported missing:

```bash
/home/sara/energy_soc_experiment_kit/kit/venv/bin/python -m pip install matplotlib==3.11.1 scikit-learn==1.9.0
```

Matplotlib is used only for figures. Do not upgrade numpy, scipy, osmnx or networkx: the simulator outputs depend on them.

## 3. Test the kit on your machine (about 10–15 minutes with 4 cores)

```bash
bash tests/selftest.sh                       # refusal, forced failures, resume, skip, validation (4 short runs)
bash scripts/01_smoke_and_regression.sh      # 16 regression + 22 smoke runs
```

`01_smoke_and_regression.sh` requires two things:

- **Regression.** Every rerun of 16 conditions from your 320-run campaign (seeds 30001 and 45001, both policies, both SOC levels, both αE, probe ON) is byte-identical to your existing run in six output files plus the workload hash. Timing columns are excluded.
- **Smoke.** The 22 smoke runs (seed 904001) reproduce the reference values computed on the kit author's machine (`tests/reference_smoke_values.csv`). Completions, energy, distance, wait, blocking, workload and fleet hashes, correlation sums and probe statistics must match.

If both pass, your machine reproduces the author's results exactly, and the probe and overrides behave as documented.

## 4. Freeze the protocols, then run

```bash
cd protocols && sha256sum experiment_A_payload.json experiment_B_fleet.json > PROTOCOL_SHA256SUMS.txt && cd ..
"$PY" bin/sample_size.py --existing /home/sara/energy_soc_campaign_runs   # optional: reproduces the n justification
bash scripts/02_run_experiment.sh B      # 960 runs, about 3.8 core-hours
bash scripts/02_run_experiment.sh A      # 2,000 runs, about 6.1 core-hours
```

Each command runs the full pipeline: matrix and estimate, launch, validation, extraction, analysis, figures, then export.

Results land in `$OUT_ROOT/experiment_B_fleet/` and `$OUT_ROOT/experiment_A_payload/`:

- `analysis/contrasts.md` and `contrasts.csv`: every prespecified contrast with mean, 95% CI, SD, d_z, p, Holm p and verdict
- `analysis/condition_summary.md`: service, energy, Wh per completion, km, wait, blocking, r, decision changes and decision-level saving per condition
- `analysis/figures/*.pdf|png`
- `validation_report.md`
- `run_level.csv`: one row per run
- `exports/<protocol>_<time>.zip`: compact archive with `SHA256SUMS.txt`

Run B first: it is shorter and answers the fleet question independently of A.

## 5. Resuming after an interruption

Run the same command again. The launcher handles every folder state:

- **Finished** (`runs/<label>/RUN_OK.json`, matching the protocol): skipped, never rerun.
- **Failed** (`RUN_FAILED.json`) or **interrupted** (no marker): the folder is moved to `_incomplete/<label>__<time>`, never deleted, and the run is redone.
- **Finished with a different spec**: the launcher stops and refuses to touch it.

Other controls:

- **Progress.** `"$PY" bin/matrix.py --protocol protocols/experiment_A_payload.json --campaign "$OUT_ROOT/experiment_A_payload"`.
- **Stopping.** Ctrl-C is safe. Runs in progress are redone next time; finished runs are kept.
- **Subsets.** `--match REGEX` on `bin/launch.py` runs a subset, for example one policy: `--match __hungarian__`.
- **Failures.** Persistent failures are listed at the end of the launch, in `campaign_log.csv`, and in `runs/<label>/RUN_FAILED.json` (reason and stderr tail). Validation fails until every expected run has `RUN_OK.json`.

## 6. Independent verification by someone else

```bash
"$PY" bin/archive.py --verify "$OUT_ROOT/experiment_B_fleet/exports/EXP_B_FLEET_<time>.zip"   # checksums
"$PY" bin/validate.py --protocol protocols/experiment_B_fleet.json --campaign "$OUT_ROOT/experiment_B_fleet"
"$PY" bin/extract.py --campaign <campaign>  &&  "$PY" bin/analyze.py --protocol <protocol> --campaign <campaign>
```

Every run folder contains everything needed to rerun it:

- `run_spec.json`: seed, overrides and settings
- `overrides_and_provenance.json`: frozen and run values of every override, app and input hashes, trial index, argv, Python version
- `stdout.txt` / `stderr.txt`
- the simulator's own `results/<run_id>/`, including `run_settings.json`, which also records the overridden constants

Rerunning one condition with the same spec reproduces it exactly.

## 7. What the validator enforces

1. Completeness against the protocol.
2. The frozen source hash in every run.
3. Overrides recorded as specified and visible in `run_settings.json`.
4. Cost settings, fleet size and request count.
5. One canonical workload per (seed, request count) across all conditions, distinct across seeds.
6. Identical initial fleets within (seed, configuration, SOC), with initial energy equal to 9,000 Wh × SOC.
7. Request accounting.
8. Probe present. Its all-round planned energy (every assignment made, including rounds the decision-level comparison excludes) equals battery withdrawal within 0.5% (observed: about 10⁻⁸ %) and equals the simulator's `assignment_events.csv` sum within 10⁻⁹ relative. The compared, unequal-cardinality and no-alternative parts must add up to it. A kit v3.0 record with unequal-cardinality rounds is `LEGACY_INCOMPLETE` (a failure) until repaired.
9. The energy term raises the mean assignment cost.
10. Blocking: none at 100% SOC (warning only), some at 25% SOC under both αE values.
11. With `--repair`: every repaired run is re-verified against its original at validation time, covering simulator outputs, workload hash and original probe fields. The repair report must belong to this protocol and campaign.
12. Coverage (information): runs and rounds with unequal assignment cardinality, which the decision-level saving excludes by definition.

## 8. Runtime overrides used (all recorded per run)

| Name | Where | Values |
| --- | --- | --- |
| `UGV_EMPTY_MASS_KG` and alias `UGV_MASS_KG` | Experiment A | 825 (frozen), 586.5, 455.8 |
| `UGV_PASSENGER_MASS_KG` | Experiment A | 80 (frozen), 100, 160 (stress) |
| `TRIAL_SEEDS` | Every run | The run's seed is appended; trial index = its position |
| `EXPERIMENT_CONFIG["V24R200"]` | Experiment B | 24 vehicles, 200 requests (S3 and S4 are used for 24/100 and 12/100) |
| Probe | Hungarian and Greedy runs | Counterfactual costing and re-solving in memory; counters restored |

`ARRIVAL_WINDOW_S` is allowed by the runner but not used by A or B.
