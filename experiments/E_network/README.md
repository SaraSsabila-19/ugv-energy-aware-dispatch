# Experiment E: external road geometry and demand compression

The uploaded historical UM-district network is embedded in `inputs_um/` unchanged. No new download is performed. Frozen UTP app and inputs are read from `~/ugv-benchmark-public`; each run gets a byte-identical copy of the original simulator and its specified network. Only the arrival window and, for UM, the parking-coordinate registry are overridden in memory. The hotspot CSV preserves row order, weights and unique node identities through a one-to-one mapping. The depot IDs and fleet allocation are unchanged. The supplied graph is real OpenStreetMap geometry; the demand and depot locations are synthetic, not observed UM demand. Routing retains the frozen bidirectional and flat-road assumptions. OSM data © OpenStreetMap contributors, ODbL (https://www.openstreetmap.org/copyright).

## Run on Ubuntu

```bash
cd ~/Downloads
unzip energy_soc_experiment_kit_v6.zip -d ~/
cd ~/energy_soc_experiment_kit_v6
sha256sum -c KIT_SHA256SUMS.txt --quiet
JOBS=1 bash run_E.sh pilot
```

The pilot runs 16 cells on one excluded seed. Look for `PILOT PASS` and `EXPORT VERIFIED`. Send the terminal output before starting the main campaign. Do not tune the protocol based on the pilot. The pilot is a technical check, not inference. A simulator-specific failure should be investigated before any confirmatory run.

After the pilot passes:

```bash
JOBS=2 bash run_E.sh run
```

Use `JOBS=1` if D is still running or CPU/memory is limited. Free space check estimates 8 MiB/run plus 512 MiB reserve (~5.5 GiB for 640). Actual runtime may be substantially greater than UTP because UM has over ten times the graph nodes and longer paths. The same command resumes; incomplete/corrupted attempts are retained under `_incomplete/`. Completed outputs are hashed and rechecked before reuse. Ctrl-C or SIGTERM stops the launcher. Separate campaign folders protect prior experiments. `bash run_E.sh status` and `bash run_E.sh pilot-status` count completion markers; `bash run_E.sh validate` revalidates and exports without launching simulations. `PY`, `REPO`, `OUT_ROOT` and `JOBS` can be overridden through environment variables. Do not install/change dependencies between pilot and main (environment identity gate). If needed, the same simulator venv should include matplotlib, scipy and numpy before the pilot starts.

Main result archive: `~/ugv_v6_campaigns/experiment_E_network/exports/EXP_E_NETWORK_*.zip`. It contains the protocol, matrix, manifest/mappings and graph, run-level data, paired seed effects, condition means, secondary intervals, primary contrasts, figures and validation report. Raw simulation records remain in the campaign directory.

## Prespecified design

640 runs = 2 networks × 2 arrival windows (1800/600 s) × 2 policies × 2 alpha levels × 40 new seeds. Fixed 12 vehicles, 100 requests, 100% SOC, 825kg cart/80kg passenger, three fixed depot identities, 30s dispatch, 60s urgency, beta 1 and SOC cost 0, normalized references 100Wh/600s. No third algorithm is substituted. Pilot = 16 runs on seed 1090001, main seeds 1101001 through 1140001 in increments of 1000. Eight simple contrasts and eight interactions, Holm corrected separately, paired t intervals and 100,000 sign-flip draws. The service guard is a descriptive check against an apparent energy reduction caused by deterioration of completion, not an adjusted joint noninferiority test. All contrasts reported regardless of significance. Less energy per run alone is not proof of better efficiency. No generalization to real UM service or network-independent causal effect of an isolated graph characteristic.

## Test record

Independently audited the uploaded archive hashes, mapping recomputation, connectivity and shortest-path metrics using a standard-library GraphML parser and Dijkstra. Offline matrix, paired workload rejection, inference/interaction, service guard, figure and checksummed export tests are provided in `tests/test_E.py`. The full real simulator could not be executed in the kit-building environment because NetworkX/OSMnx are absent; the 16-run pilot on your existing VM is mandatory. The active simulator's original source is not edited.

Experiment F: `F_measurements.md` describes the empirical calibration requirements. Its calibrated results are not available until real measurement evidence is obtained.
