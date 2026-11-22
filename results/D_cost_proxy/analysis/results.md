# Experiment D — validation and results

EXP_D_EQUIVALENCE: 1120 validated runs, 40 paired seeds; 0 native controls matched.
PASS: frozen source/input, protocol, workload/fleet pairing, candidate count, active route energy, matching and accounting.
Pilot is excluded from confirmation. Positive values: lower battery/wait/ride or higher completion. Same-state local gap is native e1 minus surrogate, descriptive.

## Equivalence to native energy weight 1

| Mass | Policy | Metric | Mean | 95% CI | Holm TOST p | Equivalent |
|---|---|---|---:|---|---:|---|
| M825_P80 | greedy | battery_pp | -1.182 | [-2.154, -0.211] | 1 | not established |
| M825_P80 | greedy | wait_s | -0.259 | [-3.695, 3.177] | 6.67e-06 | yes |
| M825_P80 | greedy | ride_s | -5.481 | [-10.204, -0.758] | 0.1506 | not established |
| M825_P80 | greedy | completed | 0.025 | [-0.026, 0.076] | 4.804e-32 | yes |
| M825_P80 | hungarian | battery_pp | -0.028 | [-0.887, 0.830] | 0.08255 | not established |
| M825_P80 | hungarian | wait_s | 0.388 | [-2.901, 3.677] | 4.127e-06 | yes |
| M825_P80 | hungarian | ride_s | -1.017 | [-4.278, 2.244] | 1.016e-05 | yes |
| M825_P80 | hungarian | completed | 0.000 | [0.000, 0.000] | 0 | yes |
| M456_P100 | greedy | battery_pp | -1.022 | [-2.045, 0.001] | 1 | not established |
| M456_P100 | greedy | wait_s | -1.830 | [-6.103, 2.443] | 0.001623 | yes |
| M456_P100 | greedy | ride_s | -7.387 | [-11.720, -3.055] | 0.4597 | not established |
| M456_P100 | greedy | completed | 0.000 | [0.000, 0.000] | 0 | yes |
| M456_P100 | hungarian | battery_pp | -0.777 | [-1.801, 0.247] | 0.9925 | not established |
| M456_P100 | hungarian | wait_s | -2.060 | [-5.492, 1.371] | 0.000154 | yes |
| M456_P100 | hungarian | ride_s | -2.737 | [-6.541, 1.067] | 0.001623 | yes |
| M456_P100 | hungarian | completed | 0.000 | [0.000, 0.000] | 0 | yes |

## Energy sweep vs time-only

| Mass | Policy | Arm | Saving pp | 95% CI | Holm p |
|---|---|---|---:|---|---:|
| M825_P80 | greedy | e025 | 1.224 | [0.159, 2.288] | 0.2285 |
| M825_P80 | greedy | e05 | 1.885 | [0.640, 3.130] | 0.05538 |
| M825_P80 | greedy | e1 | 2.366 | [1.222, 3.510] | 0.00437 |
| M825_P80 | greedy | e2 | 2.261 | [1.105, 3.417] | 0.00522 |
| M825_P80 | greedy | e4 | 1.884 | [0.463, 3.304] | 0.1171 |
| M825_P80 | greedy | pk1 | 1.183 | [-0.049, 2.416] | 0.2417 |
| M825_P80 | hungarian | e025 | 0.271 | [-0.895, 1.436] | 0.6448 |
| M825_P80 | hungarian | e05 | 0.791 | [-0.559, 2.142] | 0.4869 |
| M825_P80 | hungarian | e1 | 1.258 | [0.092, 2.423] | 0.2417 |
| M825_P80 | hungarian | e2 | 1.909 | [0.731, 3.087] | 0.03345 |
| M825_P80 | hungarian | e4 | 1.697 | [0.517, 2.877] | 0.07452 |
| M825_P80 | hungarian | pk1 | 1.229 | [0.006, 2.453] | 0.2417 |
| M456_P100 | greedy | e025 | 1.072 | [0.084, 2.060] | 0.2417 |
| M456_P100 | greedy | e05 | 1.873 | [0.761, 2.985] | 0.02624 |
| M456_P100 | greedy | e1 | 2.883 | [1.567, 4.199] | 0.00168 |
| M456_P100 | greedy | e2 | 3.790 | [2.514, 5.065] | 0.00024 |
| M456_P100 | greedy | e4 | 3.592 | [2.484, 4.699] | 0.00024 |
| M456_P100 | greedy | pk1 | 1.861 | [0.674, 3.048] | 0.03962 |
| M456_P100 | hungarian | e025 | 1.171 | [0.052, 2.289] | 0.2417 |
| M456_P100 | hungarian | e05 | 1.542 | [0.185, 2.899] | 0.2285 |
| M456_P100 | hungarian | e1 | 2.240 | [1.031, 3.448] | 0.01377 |
| M456_P100 | hungarian | e2 | 2.846 | [1.509, 4.184] | 0.004 |
| M456_P100 | hungarian | e4 | 3.568 | [2.306, 4.831] | 0.00044 |
| M456_P100 | hungarian | pk1 | 1.463 | [0.311, 2.616] | 0.131 |

## Same-state proxy diagnostics (native e1 reference trajectories)

| Mass | Policy | Action disagreement % | Residual MAE Wh | Unequal rounds per run |
|---|---|---:|---:|---:|
| M825_P80 | greedy | 6.468 | 6.767 | 0.000 |
| M825_P80 | hungarian | 6.582 | 6.747 | 0.000 |
| M456_P100 | greedy | 7.203 | 4.255 | 0.000 |
| M456_P100 | hungarian | 6.065 | 4.199 | 0.000 |

No claim of exact equivalence or optimal alpha follows from a high correlation. The Pareto comparison is descriptive; no selection or tuning on confirmatory seeds.
