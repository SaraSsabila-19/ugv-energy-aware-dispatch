# Experiment F — measured-data-informed road-load sensitivity

Final planned simulation experiment. Raw external measurements and reproducible diagnostic are included under `calibration/` (see METHOD.md). No direct physical calibration of the exact cart is claimed. The frozen base coefficient .012 is retained; low .008 and high .020 derive from the four training trips, prior to any F fleet outcomes. The same coefficient changes resistance in the energy predictor and motion execution; other constants, charging and reserve unchanged. All simulator source/input files are copied unchanged from the original UTP repo.

## Run on Ubuntu

```bash
cd ~/Downloads
unzip energy_soc_experiment_kit_v7.zip -d ~/
cd ~/energy_soc_experiment_kit_v7
sha256sum -c KIT_SHA256SUMS.txt --quiet
JOBS=1 bash run_F.sh pilot
```

24 pilot cells, one excluded seed. Wait for PILOT PASS and EXPORT VERIFIED; send the terminal output before launching 960 runs using `JOBS=2 bash run_F.sh run`. Same command resumes; corrupted/incomplete attempts are retained under `_incomplete/`. Separate output root (`~/ugv_v7_campaigns`) protects E and all prior campaigns. Use `bash run_F.sh status` or `bash run_F.sh pilot-status`. `validate` revalidates and exports without simulation. `PY`, `REPO`, `OUT_ROOT`, `JOBS` configurable. Keep environment unchanged between pilot and main. Estimated free disk required 4.25 GiB for confirmatory runs (4 MiB/run plus 512 MiB). If E is running use one job or wait for E.

## Design and results

960 = 3 road-load configurations × 2 SOC × 2 algorithms × 2 alpha × 40 independent fresh seeds. Fixed S4 UTP (12 vehicles/100 requests, 1800 s arrival, 825/80 kg, 100% or 25% SOC, three depots, normalized cost, alpha 0/1, beta 1). Pilot seed 1190001 excluded. 1201001 through 1240001 step 1000 confirmatory. 12 simple contrasts and 14 interactions (8 parameter vs BASE, 6 SOC contrasts), Holm corrected separately; 100000 paired sign-flip draws and 95% paired t intervals. Report all, including negative and inconclusive. Secondary completion, wait, passenger duration, battery per completed, distance, grid consumption, energy blocking and within-request correlations. Service guard descriptive; energy reduction that accompanies material service deterioration is not an efficiency claim.

Main export: `~/ugv_v7_campaigns/experiment_F_sensitivity/exports/EXP_F_ROAD_LOAD_*.zip`. Includes source measurements, calibration audit/replay, frozen protocol, run matrix, paired seed effects, condition means, secondary intervals, contrasts, forest plots and validation receipt. Raw simulation files remain on VM.

## Tests and limitations

Source archive checksum and trip analysis independently checked; offline design, pairing, inference, calibration and export tests provided. Actual simulator dependencies are not installed in kit-building environment; real VM pilot is mandatory. No claim that changing the fitted effective coefficient objectively improves the exact GMTLSV, or that a low/high coefficient is a physical estimate. See calibration/METHOD.md.
