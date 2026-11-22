# Experiment C reference check against the native simulator kit

Experiment C used a custom per-round intervention harness. To confirm that the harness does not alter the simulation,
the all-off (alpha_E = 0) and all-on (alpha_E = 1) references of the first four C seeds (801001-804001, fixed before
running and not selected by outcome) were rerun with the standard kit v3.1 launcher (probe disabled) for both policies.

Compared runs: 16. Fields: workload hash and battery_Wh, driving_Wh, km, completed, wait_s, grid_Wh.

**Result: PASS.** 16 of 16 runs identical (maximum absolute difference 0).

| Policy | Seed | Reference | Native battery Wh | C battery Wh | Status |
|---|---|---|---:|---:|---|
| greedy | 801001 | off | 6110.708559 | 6110.708559 | IDENTICAL |
| greedy | 801001 | on | 6170.88811 | 6170.88811 | IDENTICAL |
| greedy | 802001 | off | 5726.218356 | 5726.218356 | IDENTICAL |
| greedy | 802001 | on | 5823.031072 | 5823.031072 | IDENTICAL |
| greedy | 803001 | off | 5972.181271 | 5972.181271 | IDENTICAL |
| greedy | 803001 | on | 5888.611631 | 5888.611631 | IDENTICAL |
| greedy | 804001 | off | 5971.838463 | 5971.838463 | IDENTICAL |
| greedy | 804001 | on | 6144.771015 | 6144.771015 | IDENTICAL |
| hungarian | 801001 | off | 6023.456182 | 6023.456182 | IDENTICAL |
| hungarian | 801001 | on | 6127.532203 | 6127.532203 | IDENTICAL |
| hungarian | 802001 | off | 5644.33584 | 5644.33584 | IDENTICAL |
| hungarian | 802001 | on | 5389.580377 | 5389.580377 | IDENTICAL |
| hungarian | 803001 | off | 6078.108555 | 6078.108555 | IDENTICAL |
| hungarian | 803001 | on | 5849.205595 | 5849.205595 | IDENTICAL |
| hungarian | 804001 | off | 6351.258286 | 6351.258286 | IDENTICAL |
| hungarian | 804001 | on | 5882.317645 | 5882.317645 | IDENTICAL |

Interpretation: the C harness reproduces native trajectories exactly for these references. C's lower Greedy
whole-run estimate relative to the other replications is therefore attributable to seed sampling, not to the harness.
This is a verification step, not an additional experiment; it adds no observations to any inference.
