# Experiment C: decision impulse response (v4)

This is a separate experiment kit for the frozen FIX-19 UGV simulator, not a replacement for experiments A/B. It uses exactly the S4, 12-vehicle, 100-request, full-charge, 825/80 kg, baseline graph and demand input used previously. It never modifies the repository or earlier results; the default output root is `~/ugv_v4_campaigns`. Source and both input SHA-256 hashes are pinned to the uploaded Experiment A results.

## Run on Ubuntu

Unzip into your home directory, then run:

```bash
cd ~/energy_soc_experiment_kit_v4
sha256sum -c KIT_SHA256SUMS.txt --quiet && echo 'Kit intact'
JOBS=2 bash run_C.sh pilot
```

The pilot is required. It runs an excluded seed with both policies, complete pulse/prefix ladders and four uninstrumented control runs. The exact number of runs appears once the references finish. The pilot is a technical integration test, not reported as confirmatory evidence. It should take roughly 15–40 minutes depending on round counts and VM speed.

Only after the pilot prints `EXPORT VERIFIED` and validation PASS:

```bash
JOBS=2 bash run_C.sh run
```

This automatically validates, analyzes, plots and exports. 40 fresh seeds x 2 policies; the exact number is determined by the predeclared rule once the 160 references complete. At 50 rounds per reference this is 8,160 simulations, not 4,000; with 10–20 seconds/run it is 23–45 core-hours. At two jobs allow roughly 12–23 hours, possibly longer on VirtualBox. At 2.5 MB/run expect about 20 GB, plus incomplete attempts. Check `df -h ~` first. No early stopping based on results. To stop, press Ctrl-C; repeat the exact command to resume. Failed or corrupted exact-spec attempts are preserved in `_incomplete/` and rerun. A different protocol or kit version is refused. Check progress with `bash run_C.sh status` (`pilot-status` for pilot).

Defaults (override with environment variables if needed): `REPO=~/ugv-benchmark-public`, `PY=~/energy_soc_experiment_kit/kit/venv/bin/python`, `OUT_ROOT=~/ugv_v4_campaigns`. Requires the original simulator dependencies plus numpy, scipy and matplotlib in the existing venv. The kit is Python 3.10+ compatible, not tested here on Python 3.14.

## Results

The full campaign outputs `analysis/RESULTS.md`, `analysis/primary_contrasts.csv`, `analysis/seed_effects.csv`, `analysis/round_effects.csv`, `analysis/run_level.csv`, `analysis/response_horizons.csv`, and figures `impulse_prefix.png/pdf` and `response_horizons.png/pdf`. The horizon analysis follows planned incremental energy committed at dispatch over elapsed time following the target round; it is not an instantaneous battery-consumption curve. The final ZIP in `exports/` contains the protocol, run matrix, campaign identity, validation report, all analysis and verified checksums. Full original per-run outputs remain in `runs/`. Share the export ZIP with your reviewer. Use `bash run_C.sh validate` to rerun validation and export without launching simulations.

## Scientific design

Let E0 and E1 denote actual battery withdrawal under all-off and all-on; S=E0-E1. For every eligible matrix round k of the all-off reference, a pulse turns on alpha only at k, then reverts to off. Eligible means at least one finite candidate cost (matching the v3.1 decision probe definition). All-infeasible matrices do not advance the ordinal and cannot assign requests; their evaluation can receive the next scheduled weight. The trace is reconciled against the positive-feasible-pair rows of cost_diagnostics.csv. In the uploaded baseline A data, 5 of 400 full-charge runs had all-infeasible rounds, so this distinction is important. Pk=E0-Epulse,k. Compare sum(Pk) and S, but do not assume they add: their histories differ. S-sum(Pk) is a nonadditivity contrast, not mediation.

For every round k of the all-on reference, a prefix uses alpha=1 for rounds 1..k and then alpha=0. Let Qk be its withdrawal, with Q0=E0. Dk=Q(k-1)-Qk. The last prefix independently reproduces the all-on endpoint. Sum(Dk)=S is a mathematical identity, not evidence of amplification. Adjacent prefixes have the same pre-target policy history. The immediate local difference Lk is planned incremental route energy under alpha=0 minus alpha=1 at the target, conditional on equal assignment cardinality. Dk-Lk is a continuation residual; sum it over matched rounds. This is not a causal mediation claim about positions or deadheading. Examine actual empty pickup, depot return, productive distance, passenger distance, waiting, ride time, completions and grid energy in paired differences.

The planned energy is audited against the simulator's own assignment log; the all-round planned sum must match that log to 1e-9 relative and battery withdrawal to 0.5%, as in v3.1. All mixed schedules are recorded in the trace; run_summary's alpha column is the base CLI setting (0 for pulses/prefixes), not the active weight. The only intervention is the alpha argument to the real pair-cost calculation. Every matrix is checked against ordered pair-cost evaluations, and the trace must reconcile with simulator matrix counts and assignments. Candidate fingerprints and exact prior action traces test pre-target equality; these are not complete simulator-state snapshots. If a no-op decision changes physical/service outputs, analysis stops. No-op validation ignores assignment cost (which changes by definition) and run IDs. If the simulator does not expose compatible hooks or all-on prefix fails to match independent all-on, the pilot fails and the campaign is blocked.

The six primary tests are paired at the seed level, not the round level; 95% t intervals, sign-flip p values, Holm correction, and predeclared ±1 percentage-point practical margin. This does not establish equivalence from a nonsignificant difference. The protocol freezes the design and exact seed list. The diagnostic figures and distance endpoints are not additional confirmatory tests.

## Verification limits

The supplied A/B exports contain provenance, settings and output schemas but omit the frozen app.py and map inputs. The kit uses the same documented v3.1 pair-cost/solver hook and pinned hashes. Local tests exercise the wrapper with synthetic matrices and the analysis identities; **real simulator integration has not been tested by ChatGPT**. The pilot is deliberately fail-closed and must pass on your actual machine before the full campaign. If it fails, send the first STOP line and corresponding `stderr.txt` to ChatGPT for diagnosis. Do not change thresholds or edit the frozen simulator to force a pass.
