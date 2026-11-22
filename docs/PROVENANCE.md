# Provenance, deviations and validation status

## Frozen simulator

| File | SHA-256 |
|---|---|
| `src/frozen/app.py` (FIX-19) | `7b52bb550414469937da3098f91313b366137d43bd48b8465b840a97bffeb0a0` |
| `inputs/utp_graph.graphml` | `ebd138a83763f11172e079f40457b371be7eebcd2e3aa018aeda13d9d70114f4` |
| `inputs/hotspot_locations.csv` | `6a55a275f2ac18ab383d2efcd67a31250602503a62fa3c5bf2f3f504ae0b979d` |

The simulator file was never modified. Each kit:
- imports the simulator;
- sets the documented overrides in memory, such as appended trial seeds, masses, arrival window or rolling resistance, and new fleet/demand scenarios;
- records those overrides per run;
- archives the executed source with every run.

All campaign identity files record the same source hash. The C–F identities record CPython 3.14.4.

## Campaign → code → protocol → archive

| Campaign | Kit (in `experiments/`) | Protocol | Result archive (`archives/`) | Validation |
|---|---|---|---|---|
| Original 2×2 | `0_original_soc` (kit v2) | `make_matrix.py --seeds 21001:60001:1000` | summary only (see below) | `check_runs.py` PASS at the time; summary in `results/0_original_soc/` |
| A | `A_B_payload_fleet` (kit v3.1) | `protocols/experiment_A_payload.json` | `EXP_A_PAYLOAD_20261121T152221.zip` | PASS, 2,000/2,000 |
| B | run with kit v3.0, repaired and analysed with kit v3.1 | `protocols/experiment_B_fleet.json` | `EXP_B_FLEET_repaired_20261121T051808.zip` | PASS, 960/960 (10 verified repaired probe records) |
| C | `C_dynamics` (kit v4) | `protocols/experiment_C.json` | `EXP_C_IMPULSE_20261122T073630.zip` | PASS, 8,013 (160 references, 7,853 interventions) |
| D | `D_cost_proxy` (kit v5) | `protocols/experiment_D.json` | `EXP_D_EQUIVALENCE_20261122T124719.zip` | PASS, 1,120/1,120 |
| E | `E_network` (kit v6) | `protocols/experiment_E.json` | `EXP_E_NETWORK_20261122T165310_397512.zip` | PASS, 640/640 |
| F | `F_road_load` (kit v7) | `protocols/experiment_F.json` | `EXP_F_ROAD_LOAD_20261122T165338_661310.zip` | PASS, 960/960 |

Each kit is byte-identical to its archived zip in `archives/provenance/`, and each kit protocol is identical to the protocol exported with its results. `verification/verify_repository.py` checks both.

The A and B protocols were fixed before any confirmatory run. Their protocol JSON files are byte-identical between kit v3.0 and v3.1. The C–F protocols record their protocol hashes in `campaign_identity.json`. Pilot seeds were excluded from every confirmatory set:
- C: 951001;
- earlier exploratory and pilot seeds, listed under `excluded_seeds` in the A/B protocols;
- D, E and F: each kit's pilot protocol.

## Deviations and corrections

1. **Experiment B probe accounting (2026-11-21).**
   - **What happened:** the kit v3.0 decision probe added planned active energy only in dispatch rounds in which both matchings assigned the same number of requests. The validator compared that partial sum with total battery withdrawal.
   - **Scope:** ten Greedy runs had such unequal-cardinality rounds, and their probe validation failed. Hungarian cannot produce unequal cardinality, because it maximises cardinality first.
   - **Repair:** kit v3.1 records all-round energy separately and checks it against battery withdrawal (0.5%) and against the simulator's assignment log (1e-9). The ten runs were re-executed from unchanged specifications into a separate repair folder. Each one reproduced every simulator output, the workload hash and all original probe fields exactly.
   - **Effect:** the decision-level estimand `sdec_pct` and all simulator outcomes are unchanged. The original records are preserved.
   - **Details:** `results/B_fleet/repair_report.md`, `DEVIATIONS_entry.md`, `original_validation_report.md` and `experiments/A_B_payload_fleet/protocols/DEVIATIONS.md`.
2. **Unequal-cardinality rounds in A.** Two runs had one such round each. They are excluded from the same-state comparison by definition and retained in all run-level outcomes.
3. **Decision-level saving definition.** `sdec_pct` = 100 × (planned ΔE of the time-only choice − planned ΔE of the energy-weighted choice), summed over equal-cardinality rounds and divided by the run's battery withdrawal. It is a same-state diagnostic, not a run-level treatment effect.
4. **Experiment D native controls** were run in the pilot only, not in the confirmatory campaign.
5. **Experiment C reference identity.** The C harness switches αE per dispatch round. Its validator checked trace, endpoint and prefix identities within the harness. In addition, 16 native-kit reruns of C's all-off and all-on references were compared with C's records: 4 seeds (801001–804001, the first four in the protocol, fixed before running), 2 policies and αE 0/1. All 16 were identical in workload hash, battery, driving and grid energy, distance, completions and waiting time (`verification/c_native_reference_check/`). This was a verification step on 22 Nov 2026, after the campaign; it adds no observations to any inference.
6. **Post hoc replication synthesis.** `analysis/synthesis.py` pools the identically specified canonical cell across the seven independent seed sets. It was not prespecified and does not change any protocol verdict. The original 2×2 enters with an approximate denominator (the condition-mean αE = 0 withdrawal).

## What is not included

- **Original 2×2 raw runs.** The per-run directories of the original 320-run campaign are not included. `results/0_original_soc/` contains its seed-level paired differences, summary and mechanism outputs, which support every number reported from it. Kit v2 reproduces the campaign: an independent rerun of all 320 runs matched every reported summary value.
- **Large trace tables.** The 22 MB per-round diagnostics table of D and the run matrices of C–F are inside their archives, not in `results/`.

## Paths inside the kits

Kits are kept byte-identical to the versions that ran, so they contain their original default paths:
- `/home/sara/...` defaults, overridable through `REPO`, `PY` and `OUT_ROOT`;
- in the exploratory `experiments/0_original_soc/probes/` scripts and in kit v3.1's `TESTED.md`, the paths of the analysis sandbox in which they were developed and tested.

The probe scripts were exploratory diagnostics. They did not produce any confirmatory result.

## Archive checksums

`archives/ARCHIVES.sha256` lists SHA-256 checksums of all archives. Each result archive also contains its own `SHA256SUMS.txt` covering every member. The A and B archives contain 30,025 and 14,475 checksummed members.
