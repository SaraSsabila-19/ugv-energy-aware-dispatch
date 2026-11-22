# Energy-weight × initial-SOC experiment kit

Runs the S4 setup (12 UGVs, 100 requests, depots P02/P08/P16) for Hungarian and Greedy with the energy term off and on (αE = 0/1, βT = 1, γSOC = 0) at 100% and 25% initial SOC, using the frozen FIX-19 `app.py` unchanged (SHA-256 `7b52bb55…0a0`).

**Why a wrapper:** `app.py` only accepts `--trial-index 0–19` (seeds 1001–20001). Those seeds were used for the campaigns and to choose 25% SOC, so the new experiment needs fresh seeds. `wrap_run.py` imports the frozen module, appends new seeds to `TRIAL_SEEDS` in memory, then calls `headless_main()`. The file on disk is untouched, so every archived `backend_source.py` still hashes to the frozen identity. Trial index 20 is the first new seed, 21 the second, and so on.

Verified on 2026-11-19 with CPython 3.13.18 (the paper used 3.14.4), numpy 2.4.6, scipy 1.17.1, osmnx 2.1.0, pandas 3.0.3, networkx 3.6.1, fastapi 0.137.0 and scikit-learn 1.9.0:

- Archived S4/Hungarian/seed 3001 runs reproduced exactly with αE = 1 (5,843.207368 Wh, 104.544 km, workload hash `30a1ecf7…`) and αE = 0 (6,153.641206 Wh, 99 completions). The difference matches the archived ablation row (−310.433838 Wh) to six decimals.
- A 4-seed pilot (seeds 91001–94001, 32 runs) and a 1-seed smoke test (99001, 8 runs) passed every check below. **Exclude these seeds from the confirmatory set.** `make_matrix.py` refuses them.

## Setup
```bash
python3 -m venv venv && . venv/bin/activate
pip install numpy==2.4.6 scipy==1.17.1 networkx==3.6.1 osmnx==2.1.0 pandas==3.0.3 \
            fastapi==0.137.0 pydantic==2.13.4 httpx==0.28.1 starlette==1.3.1 scikit-learn==1.9.0
export PY=$PWD/venv/bin/python        # interpreter used by run_one.sh
REPO=/path/to/ugv-benchmark-public    # repository root (contains src/frozen/app.py, inputs/)
OUT=/path/to/new_campaign_runs        # empty folder, outside the repository
```
Note: `scikit-learn` is missing from the repository's `requirements.txt`, but osmnx needs it for `nearest_nodes` on this graph. Without it, the first run fails with an ImportError.

## Run (40 new seeds = 320 runs; about 10 s per run, so roughly 27 min on 2 cores)
```bash
python3 make_matrix.py --seeds 21001:60001:1000 > runs.txt      # 320 lines
cat runs.txt | xargs -P "$(nproc)" -L 1 ./run_one.sh "$REPO" "$OUT"
$PY -I check_runs.py "$OUT" 320                                   # must print PASS
$PY -I analyze_2x2.py "$OUT" > results_2x2.md                     # writes paired_differences_by_seed.csv to cwd
```
For 20 seeds (160 runs), use `--seeds 21001:40001:1000` and `check_runs.py "$OUT" 160`. Reruns skip finished conditions (a `DONE` marker in each folder).

## What `check_runs.py` enforces
1. Every run archives the frozen source hash.
2. One canonical workload hash per seed across all 8 conditions, and different hashes across seeds.
3. Identical initial fleets (vehicle, depot, initial Wh) within each SOC level, at 9,000 Wh or 2,250 Wh per vehicle.
4. Cost settings βT = 1, γSOC = 0, normalized mode, references 100 Wh and 600 s, 12 vehicles, 100 requests, depots P02;P08;P16. Recorded αE and SOC agree with the run label.
5. Switching the energy term on raises the mean assignment cost at 100% SOC, which shows the cost actually changed.
6. The reserve rule blocks candidate pairs at 25% SOC under **both** αE = 0 and αE = 1, so feasibility still applies with the energy term off. There is zero blocking at 100%.

## Analysis (`analyze_2x2.py`)
Per seed and policy: D_soc = Y(αE=1) − Y(αE=0), and the interaction I = D_25 − D_100.
- **Primary family (Holm over 4):** I for completions and I for battery Wh, for Hungarian and for Greedy. The exact sign-flip test uses dynamic programming for integers; for Wh it is exact up to n = 22 and Monte Carlo above that (default 10⁶ draws). Intervals are paired 95% t intervals. The script also reports whether each interval lies inside the pre-stated margins (±1 completion per 100; ±100 Wh).
- **Reported together:** completions, battery Wh per run, and Wh per completed request (ratio of sums), with a paired seed-bootstrap CI for the ratio change.
- Simple effects at each SOC level, plus distance and capped wait, are descriptive.
