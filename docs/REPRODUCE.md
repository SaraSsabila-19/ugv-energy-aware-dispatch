# Reproduction guide

There are three levels of reproduction, from minutes to days of compute. Every command runs from the repository root unless a `cd` is shown.

## 0. Environment

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt            # verification and analysis
python -m pip install -r requirements-lock.txt       # exact campaign environment (CPython 3.14.4), needed for simulation
export REPO="$PWD"                                   # every kit reads the simulator from $REPO/src/frozen and $REPO/inputs
export PY="$(command -v python)"
export OUT_ROOT="$HOME/ugv_reproduction"             # new campaign folders are created here; never inside the repository
export JOBS=2
```

The simulator also needs `PYTHONHASHSEED=0`, `V2_DEPOT_LAYOUT=three` and `V2_THREE_DEPOT_IDS=P02,P08,P16`. Each kit's launcher sets these itself, so don't run `src/frozen/app.py` by hand for campaign runs.

## 1. Verify the published results (minutes, no simulation)

```bash
python verification/verify_repository.py        # 46 checks; recomputes all reported contrasts from run-level data
python analysis/synthesis.py                     # post hoc replication synthesis, analysis/output/
```

Each campaign's own analysis can also be regenerated from its exported run-level table. The kits read their campaign folders, so point them at an unpacked archive:

```bash
mkdir -p /tmp/expA && unzip -q archives/EXP_A_PAYLOAD_20261121T152221.zip -d /tmp/expA
ls /tmp/expA/EXP_A_PAYLOAD_20261121T152221/runs_compact | head   # per-run outputs, settings and probe records
```

## 2. Re-execute sample runs (about 1 minute)

```bash
python verification/reproduce_sample_runs.py                       # Experiment A, seed 601001, 4 runs
python verification/reproduce_sample_runs.py --seeds 601001 650001  # any seeds from 601001-700001
```

The runs are written to `reproduced_runs/`, which git ignores. Every run-level value is compared with `results/A_payload/run_level.csv`.

The Experiment C native reference check, which reruns 16 runs, can be repeated with:

```bash
python experiments/A_B_payload_fleet/bin/launch.py --protocol verification/c_native_reference_check/protocol_c_native_check.json \
  --repo "$REPO" --out "$OUT_ROOT/c_native_check" --python "$PY" --jobs "$JOBS"
python experiments/A_B_payload_fleet/bin/extract.py --campaign "$OUT_ROOT/c_native_check"
cp "$OUT_ROOT/c_native_check/run_level.csv" verification/c_native_reference_check/native_run_level.csv
python verification/c_native_reference_check/compare_c_references.py      # expected: PASS, 16 of 16 identical
```

## 3. Re-run a complete campaign (hours to days)

Each kit is byte-identical to the version that produced the published campaign. Its own README documents safeguards, resume behaviour and expected output. Pilots use excluded seeds and are integration tests only.

| Campaign | Commands | Runs | Approx. compute |
|---|---|---:|---|
| Original 2×2 | `cd experiments/0_original_soc && python3 make_matrix.py --seeds 21001:60001:1000 > runs.txt && cat runs.txt \| xargs -P "$JOBS" -L 1 ./run_one.sh "$REPO" "$OUT_ROOT/soc_2x2" && $PY -I check_runs.py "$OUT_ROOT/soc_2x2" 320 && $PY -I analyze_2x2.py "$OUT_ROOT/soc_2x2"` | 320 | about 1 core-hour |
| A | `cd experiments/A_B_payload_fleet && bash scripts/02_run_experiment.sh A` | 2,000 | about 6 core-hours |
| B | `cd experiments/A_B_payload_fleet && bash scripts/02_run_experiment.sh B` | 960 | about 4 core-hours |
| C | `cd experiments/C_dynamics && bash run_C.sh pilot && bash run_C.sh run` | 8,013 | 23–45 core-hours |
| D | `cd experiments/D_cost_proxy && bash run_D.sh pilot && bash run_D.sh run` | 1,120 | about 4 core-hours |
| E | `cd experiments/E_network && bash run_E.sh pilot && bash run_E.sh run` | 640 | about 3–6 core-hours |
| F | `cd experiments/F_road_load && bash run_F.sh pilot && bash run_F.sh run` | 960 | about 3 core-hours |

Notes:

- **Kits A and B:** `scripts/config.sh` and the run scripts default to the author's original paths (`/home/sara/...`, `~/ugv-benchmark-public`). The exported `REPO`, `PY` and `OUT_ROOT` above override them. Kits A and B also read `EXISTING`, the original 2×2 campaign folder; it is used only by `01_smoke_and_regression.sh`.
- **Experiment B:** it was originally run with kit v3.0 (`archives/provenance/energy_soc_experiment_kit_v3.0.zip`). Ten runs' probe records were then repaired and verified with kit v3.1. Rerunning B with v3.1 produces the corrected probe records directly. See [PROVENANCE.md](PROVENANCE.md).
- **Experiment E:** `experiments/E_network/inputs_um/` holds the prepared second-network inputs. `prepare_E.py` documents how they were built from OpenStreetMap; the manifest records the snapshot date.
- **Experiment F:** `experiments/F_road_load/calibrate_F.py` regenerates the road-load range from the bundled ESOGU-ML5EV archive.
- **Kit v6 README:** it contains a note that F's results await real measurements. That note predates kit v7, which implemented F with the external dataset.
- **Disk space:** full campaigns write about 2.5–8 MB per run.

## Expected exactness

All campaign outputs are deterministic given the seed and environment. Reruns on CPython 3.14.4 with `requirements-lock.txt` are expected to be bit-identical. On CPython 3.13 the simulator outputs were bit-identical in our checks. Only one derived floating-point aggregate (a correlation sum of squares) differed, by 1.9e-16 relative, because of summation order.
