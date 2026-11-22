# What was tested before delivery, and what was not

## Kit v3.1 (probe accounting correction), tested 2026-11-21

Why v3.0's testing missed the defect: none of the roughly 228 runs used to test v3.0 contained a round in which the two matchings assigned different numbers of requests. The validator's comparison of a comparison-only sum with the run total therefore never failed, and the statement in item 3 below ("planned energy equals battery withdrawal") held only for those runs. To test the v3.1 correction, I first reproduced the failure.

1. **Reproduction.** I ran a 160-run test campaign with the unchanged v3.0 package: seeds 920001–939001 (not used by any protocol), 12/100 and 24/200, Hungarian and Greedy, 25% SOC, αE 0/1, probe on. Three Greedy 12/100 runs had one unequal-cardinality round each. Their legacy plan energy was 2.5–4.8% below battery withdrawal, the v3.0 validator failed exactly these three, and in all three the simulator's `assignment_events.csv` matched battery withdrawal within 4e-9 %. No Hungarian run had an unequal round. The v3.0 code lines are `runner.py` 155–164 (accumulation only in the equal-cardinality branch) and `validate.py` 78 (comparison with total withdrawal).
2. **Identification.** `repair.py --identify-only` listed the same 3 of 160 runs and wrote nothing.
3. **Repair.** `scripts/03_repair_experiment.sh` reran only those 3 runs (26 s in total) into a separate folder. All 3 were VERIFIED: 9 simulator output files (timing columns excluded), workload hash, the frozen source and all 13 schema-1 probe fields identical to the originals, and the corrected accounting PASS (all-round planned energy vs battery: at most 4e-9 %). Full validation of all 160 runs then gave PASS, followed by extract, analyze, figures, export and export verification (2,437 files, 0 mismatches).
4. **Originals preserved.** SHA-256 of all 5,446 files in the original campaign was identical before and after every v3.1 operation: identification, validation, the refused launch, the refused extract/analyze/figures/archive, repair, and validation with `--repair`.
5. **Estimand unchanged.** I compared the merged run-level table with a v3.0 extraction of the same records. `sdec_pct` and 57 other shared columns are identical as text for all 160 runs. Only `plan_vs_battery_pct` differs, in exactly the 3 repaired runs, and by design: it now uses all-round energy. Fifteen paired contrasts (sdec, battery energy and completions by policy and configuration, including the cells containing the repaired runs) gave byte-identical `contrasts.csv` with v3.0 and v3.1.
6. **Corrected runner on fresh runs.** I ran the same 160 conditions again with the v3.1 runner. Simulator outputs, workload hashes and all 13 legacy probe fields were identical to the v3.0 runs in all 160, so the new probe code does not perturb any simulation. Schema-2 accounting passed natively, including the 3 runs with unequal rounds. Contrasts were byte-identical to item 5. Run-level values agree with the repaired view except for floating-point summation order (at most 1.5e-11 Wh) and wall-clock timing columns.
7. **Accounting rule (10 unit cases).** A schema-1 record with unequal rounds is `LEGACY_INCOMPLETE` even when its gap is below 0.5% (your tenth run). A genuine 1% gap fails, 0.49% passes and 0.51% fails (threshold unchanged at 0.5%). A disagreement of 1e-6 with `assignment_events` fails. Schema-2 parts must add up, and a round without an alternative fails.
8. **No suppression via the repair folder.** Four tampered copies of the repair folder were all rejected by `validate --repair`, each with a FAIL that names the run:
   - a changed simulator value in a repaired run;
   - a changed legacy probe field;
   - a report entry marked MISMATCH;
   - a report pointing to another campaign.

   The rejected repaired record falls back to the original, which also fails.
9. **Repair safety.**
   - A second invocation skips finished reruns.
   - SIGTERM during reruns exits 130 with no simulator processes left; rerunning completes the repair (3/3 VERIFIED).
   - Refused: a repair folder inside the campaign (nothing created), a non-empty foreign folder, a repair folder of another protocol, and a concurrent repair (lock).
   - The v3.1 launcher refuses to add runs to a v3.0 campaign and leaves it unchanged.

**Not verified for v3.1:**

- The repair on your actual Experiment B data (10 runs at 24/200 and 12/100, CPython 3.14.4). The repair verifies itself: any run that does not reproduce its original exactly is reported as MISMATCH and validation fails.
- Behaviour on CPython 3.14.4 and the default `/home/sara` paths (as for v3.0; `01_smoke_and_regression.sh` checks your machine).

**Fresh-unzip checks of the delivered v3.1 zip** (paths supplied through environment variables):

- `KIT_SHA256SUMS.txt` verified; protocol JSON files byte-identical to v3.0.
- `00_check_environment.sh`.
- `03_repair_experiment.sh` on the v3.0 test campaign: 3/3 VERIFIED, 160-run validation PASS, export 0 mismatches, run-level identical to the earlier repair, all 5,446 original files byte-identical afterwards.
- `tests/selftest.sh`: all six steps passed.
- `01_smoke_and_regression.sh`: 16 regression runs identical to your 320-run campaign and 22 smoke runs identical to the reference values, all with the schema-2 probe.
- `02_run_experiment.sh tests/selftest_a.json`: the 60-run Experiment A miniature through the standard pipeline, with validation PASS, figures, and an export with 0 mismatches; all 60 probe records are schema 2.

## Kit v3.0

The kit was tested on the author's machine: Linux x86-64 cloud VM with 2 cores, CPython 3.13.18, numpy 2.4.6, scipy 1.17.1, networkx 3.6.1, osmnx 2.1.0, pandas 3.0.3, fastapi 0.137.0, pydantic 2.13.4, httpx 0.28.1, scikit-learn 1.9.0 and matplotlib 3.11.2. Your recorded environment is CPython 3.14.4.

### Verified

1. **Frozen source.** `app.py` is never modified. Every run archives `backend_source.py` with SHA-256 `7b52bb55…0a0`, and the validator re-checks it.
2. **Exact regression against your campaign.** 16 conditions of the 320-run energy weight × SOC campaign were rerun with the v3 runner and the probe on: seeds 30001 and 45001 × Hungarian and Greedy × 100% and 25% SOC × αE 0 and 1. All were byte-identical in `run_summary`, energy feasibility, request results, wait diagnostics, pool energy and vehicle results (timing columns excluded), and had identical workload hashes.
   - The comparison was against my independent rerun of your campaign. That rerun had already matched every number in your summary exactly.
   - These seeds had trial indices 29 and 44 in v2 but 20 in v3, so trial-index independence is also confirmed.
3. **Probe non-interference.** Runs with the probe reproduce runs without it, including all energy-blocking counters at 25% SOC. The planned energy of the chosen insertions equals battery withdrawal within 10⁻⁸ % in every probed run (over 200 runs, all configurations).
4. **Overrides.** Payload masses reach both prediction and execution, appear in `run_settings.json`, and are recorded in `overrides_and_provenance.json`. Energy per km changes as the motion model predicts (`bin/physics.py`).
5. **New configurations.** 24 UGVs / 200 requests runs as a registered scenario. 12 and 24 UGVs with 100 requests receive identical request sets for the same seed. Vehicles spread over the three depots.
6. **Full pipeline.** Launch, validate (all ten checks PASS), extract, analyze, figures, archive and archive verification on:
   - a 60-run miniature of Experiment A (seeds 905001–907001, all 36 contrasts);
   - a 72-run miniature of Experiment B (seeds 908001–910001, all 30 contrasts);
   - the 4-run tiny protocol, through `scripts/02_run_experiment.sh`.

   The exact sign-flip test was exercised on integer and half-integer (200-request) lattices, and Holm and the verdict rules were exercised in every family. Figures were inspected visually and their layout corrected.
7. **Safety.**
   - Refusal to write into a non-empty foreign folder.
   - Forced failures (1-second timeout) detected and recorded in `RUN_FAILED.json`.
   - Resume moves failed and interrupted attempts to `_incomplete/` without deleting them.
   - Finished runs are skipped.
   - A second launcher on the same campaign is refused (file lock).
   - SIGTERM or Ctrl-C stops running simulations, marks them "interrupted by user", leaves no orphan processes and exits 130.
   - A changed byte inside an export zip is detected by `archive.py --verify`.
8. **User-facing scripts, run from a fresh copy of the kit** with paths supplied through environment variables: `00_check_environment.sh`, `tests/selftest.sh` (all six steps), `01_smoke_and_regression.sh` (16 regression and 22 smoke runs, 0 differences) and `02_run_experiment.sh tests/selftest_tiny.json`. The graph-file fallback (`utp_graph.graphml.xml`) was exercised.
9. **Sample size.** `bin/sample_size.py` reproduces the protocols' variance-based numbers from the 320-run campaign layout.
10. **Paths.** No `/home/claude` path remains anywhere in the kit. Defaults in `scripts/config.sh` point to your folders, and all can be overridden.

### Not verified

1. **Your machine.** Exact reproduction of the new configurations (payload overrides, 24/200 scenario, probe) on CPython 3.14.4. Frozen configurations already matched between 3.13 and 3.14 in the 320-run campaign. `01_smoke_and_regression.sh` tests both on your machine; run it first.
2. **The default paths** `/home/sara/...`. They could not exist here. The scripts were run with the same variables pointing elsewhere.
3. **Full campaigns.** The 2,000-run and 960-run campaigns were not run: confirmatory seeds were deliberately not executed, so no confirmatory outcome has been seen. Runtime and disk figures are extrapolated from about 250 test runs.
4. **Long-run behaviour.** Behaviour under disk-full conditions, a power loss during a file write (outputs are written by the simulator; `RUN_OK.json` is written atomically last), and parallel jobs above 2 (logic is identical; not timed).
5. **Matplotlib 3.11.1.** The README pins 3.11.1 to match your original environment snapshot; the tests used 3.11.2.
6. **Interpretation.** Nothing here establishes the physical accuracy of the energy model or external validity beyond the campus network.
