# Experiment C — validation and results

Protocol: EXP_C_IMPULSE; 8013 validated runs; 40 seeds; 7853 target comparisons.
PASS: source/input identity, matched workloads/fleets, schedule, trace accounting, pre-target equality, target candidate state, no-op checks, prefix endpoint and telescoping.

Positive values denote savings (off minus on). Percentage points use the all-off battery denominator. Pilot is excluded from confirmatory inference.

| Policy | Estimand | Mean pp | 95% CI | Holm p | Margin |
|---|---|---:|---|---:|---|
| greedy | whole_pct | 0.314 | [-0.771, 1.399] | 1 | inconclusive |
| greedy | nonadditivity_pct | 1.912 | [-1.484, 5.309] | 0.7907 | inconclusive |
| greedy | prefix_continuation_pct | 0.068 | [-1.072, 1.208] | 1 | inconclusive |
| hungarian | whole_pct | 1.500 | [-0.108, 3.108] | 0.3364 | inconclusive |
| hungarian | nonadditivity_pct | 3.826 | [0.322, 7.331] | 0.1787 | inconclusive |
| hungarian | prefix_continuation_pct | 1.045 | [-0.568, 2.658] | 0.788 | inconclusive |

Unequal-cardinality prefix comparisons: 0 (excluded only from local/continuation estimands, not global effects).
Prefix sum equals whole saving by construction, not evidence of additivity. Pulse sum is a distinct, non-additive estimand. Continuation residual is an accounting contrast; it does not identify mediation by deadheading. Distance categories and service changes are descriptive.
Candidate fingerprint and pre-target trace establish observed matching history, not a formal full-state snapshot.
