# Kit v3.1: probe accounting repair for Experiment B, then Experiment A

## What was wrong (confirmed in the code)

In kit v3.0, `ugvkit/runner.py` added `plan_energy_active_Wh` only in dispatch rounds where the energy-term matching and the time-only matching assigned the **same number** of requests. Those are the rounds used for the decision-level comparison (`sdec_pct`).

`ugvkit/validate.py` then compared this comparison-only sum with the run's **total** battery withdrawal. In a run with one or more unequal-cardinality rounds, the sum omits those rounds' assignments and the check fails.

- Only Greedy can produce unequal cardinality. Hungarian maximises cardinality first, and feasibility does not depend on αE, so both of its matchings always have the same size.
- The simulations themselves are unaffected. The simulator's own `assignment_events.csv` sums to the battery withdrawal in every run.
- `sdec_pct` is unaffected: its definition always used equal-cardinality rounds only.

## What v3.1 changes

| File | Change |
| --- | --- |
| `ugvkit/runner.py` | Probe schema 2. All schema-1 fields are unchanged in meaning and value. New: `all_rounds_active_energy_Wh` (every assignment made), `unequal_rounds_*` (the excluded rounds, active and alternative), `rounds_without_alternative` |
| `ugvkit/probe.py` (new) | One accounting rule shared by validator, extractor and repair. All-round planned energy must equal battery withdrawal within 0.5% (threshold unchanged) and the simulator's `assignment_events` sum within 1e-9 relative; schema-2 parts must add up. Schema-1 records with unequal rounds are reported as `LEGACY_INCOMPLETE` (a failure), never passed |
| `ugvkit/validate.py`, `extract.py`, `analyze.py`, `figures.py`, `archive.py` | Use the shared accounting; `--repair DIR` merges verified repaired probe records and writes all outputs to the repair folder. New run_level columns: `all_rounds_active_E_Wh`, `events_E_Wh`, `unequal_*`, `compared_energy_share_pct`, `probe_accounting`, `probe_source`. `sdec_pct` is computed exactly as before |
| `ugvkit/repair.py` (new), `scripts/03_repair_experiment.sh` (new) | Targeted rerun of only the affected runs, with per-run verification against the originals |
| `ugvkit/validate.py` (with `--repair`) | Re-verifies every repaired run against its original at validation time; the stored "VERIFIED" status alone is not trusted |
| `ugvkit/launch.py` | Refuses to add v3.1 runs to a campaign that already contains v3.0 probe records |
| All v3.1 tools | Treat a v3.0 campaign as read-only. Without `--repair`, the validator only prints its report; extract, analyze, figures and archive refuse to run |
| Protocol JSON files | **Unchanged** (byte-identical to v3.0), so your recorded protocol hashes remain valid |

## Exact commands (Ubuntu)

The v3.1 kit unpacks into its own folder; your v3.0 kit and all results stay where they are.

```bash
cd ~/Downloads
unzip energy_soc_experiment_kit_v3.1.zip -d ~/
cd ~/energy_soc_experiment_kit_v3.1
sha256sum -c KIT_SHA256SUMS.txt --quiet && echo "kit intact"

# The protocols must be byte-identical to the ones you ran B with:
(cd protocols && sha256sum -c ~/energy_soc_experiment_kit_v3/protocols/PROTOCOL_SHA256SUMS.txt)
# if you never created PROTOCOL_SHA256SUMS.txt, compare the files directly instead:
cmp protocols/experiment_B_fleet.json ~/energy_soc_experiment_kit_v3/protocols/experiment_B_fleet.json && \
cmp protocols/experiment_A_payload.json ~/energy_soc_experiment_kit_v3/protocols/experiment_A_payload.json && echo "protocols identical"
```

Paths come from `scripts/config.sh` (the same defaults as v3.0). If you changed `OUT_ROOT`, `JOBS` or other settings for v3.0, set them the same way here.

If your Experiment B folder is not `~/ugv_v3_campaigns/experiment_B_fleet`, add `CAMPAIGN=/path/to/it` in front of the commands below.

### Step 1: see which runs are affected (runs nothing, writes nothing)

```bash
source scripts/config.sh
"$PY" bin/repair.py --protocol protocols/experiment_B_fleet.json \
  --campaign "$OUT_ROOT/experiment_B_fleet" --repair-out /tmp/ignored --identify-only
```

Expected: 10 runs listed, Greedy only, including the run whose gap was below 0.5%. v3.1 treats any v3.0 record with unequal-cardinality rounds as incomplete, whatever its gap. For each, the list shows the unequal rounds and the legacy gap, and the simulator's assignment events agree with battery withdrawal to about 1e-8 %.

### Step 2: repair, revalidate the full 960, re-analyse (about 2–5 minutes)

```bash
bash scripts/03_repair_experiment.sh B
```

This reruns only the affected runs into `~/ugv_v3_campaigns/experiment_B_fleet_probe_repair_v3.1/`, verifies each one, validates all 960 runs, and writes run_level, analysis, figures and an export there.

Success means:

- `repair_report.md`: every affected run is **VERIFIED**. Simulator outputs (9 files), workload hash and all original probe fields are identical, and the corrected accounting passes.
- `validation_report.md`: overall **PASS** for all 960 runs. The `coverage` line reports the unequal-cardinality rounds.
- `analysis/contrasts.md`: estimates identical to your original analysis, because neither `sdec_pct` nor any simulator outcome changed. Check it with step 3.

Then append the generated deviation text to your log:

```bash
cat ~/ugv_v3_campaigns/experiment_B_fleet_probe_repair_v3.1/DEVIATIONS_entry.md >> protocols/DEVIATIONS.md
```

### Step 3 (only if you produced a v3.0 analysis by hand): confirm it did not change

The v3.0 script stopped at the failed validation, so normally no v3.0 analysis exists and this step is skipped. If you ran `extract.py` and `analyze.py` from kit v3.0 yourself during the diagnosis:

```bash
diff <(cut -d, -f1-12 ~/ugv_v3_campaigns/experiment_B_fleet/analysis/contrasts.csv) \
     <(cut -d, -f1-12 ~/ugv_v3_campaigns/experiment_B_fleet_probe_repair_v3.1/analysis/contrasts.csv) \
  && echo "contrast estimates unchanged"
```


### Step 4: Experiment A with the corrected probe

```bash
bash tests/selftest.sh                       # v3.1 safety checks (about 2–3 minutes)
bash scripts/02_run_experiment.sh A          # 2,000 runs, probe schema 2 from the first run
```

Run A from the **v3.1** folder. The launcher refuses to mix probe schemas if a v3.0-started A campaign exists.

## Guarantees

- **Originals untouched.** The original campaign folder is opened read-only. Nothing in it is moved, rewritten or deleted, including its v3.0 validation report.
- **Only affected runs rerun.** Affected runs are identified from their own records. With `--identify-only` nothing runs.
- **Repairs resume safely.** Interrupted repairs resume like launches. A second repair on the same folder is refused while one is running.
- **No suppressed discrepancies.** A repaired run that differs from its original in any simulator output or original probe field is marked MISMATCH and is not used; validation then fails.
