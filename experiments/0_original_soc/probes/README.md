# Round-2 probe scripts (exploratory analyses)

All three probes run the frozen `app.py` unchanged; overrides happen in memory and are recorded in each run's settings.
Paths in the `.sh` and analysis scripts point to the reviewer's working folders (`/home/claude/...`);
edit `SRC`, the venv path and the output folders before use.

| Script | What it does |
| --- | --- |
| `wrap_probe.py`, `run_probe.sh` | Decision-sensitivity probe. At every dispatch round, also costs each pair under the other alpha_E in the same fleet state. Solves both matrices with the same algorithm and records whether the matching or the chosen insertion order would differ. Decisions and outputs are unchanged (80/80 probe runs matched the confirmatory runs exactly); pair-evaluation diagnostic counters are doubled in probe runs |
| `probe_summary.py` | Aggregates the probe statistics and checks that probe runs equal the confirmatory runs |
| `wrap_surge.py`, `run_surge.sh` | Overrides `ARRIVAL_WINDOW_S` (temporal demand concentration; 600 s used) |
| `run_beta.sh` | Kit runner with `BETA` env var, e.g. `BETA=0` for an energy-only objective |
| `mechanism.py` | Energy decomposition, distance regression, pooled within-request r, failure timing, energy budget, per-seed spread |
| `explore.py` | Summarises the surge and energy-only probes against the confirmatory runs |

Seeds used: confirmatory 21001–60001; decision probe on 21001–30001; energy-only probe on 21001–28001; surge probe on 81001–88001.
`round2_outputs/` holds the reviewer's reproduction outputs: `results_2x2.md`, `mechanism_out.txt`, `probe_summary.txt`, `exploratory_probes.txt` and `paired_differences_by_seed.csv`.
