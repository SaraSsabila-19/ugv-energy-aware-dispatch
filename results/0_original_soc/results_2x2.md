# Energy-weight x initial-SOC experiment: 40 matched seeds, policies ['greedy', 'hungarian']

## Primary family: interaction I = (alpha1-alpha0 at 25% SOC) - (alpha1-alpha0 at 100% SOC), Holm over 4

| Policy | Outcome | Mean I | 95% t CI | SD | sign-flip p | Holm p | CI inside +/- margin? |
|---|---|---|---|---|---|---|---|
| greedy | completions/100 (=pp) | +0.00 | [-0.91, +0.91] | 2.85 | 1 (exact) | 1 | yes (+/-1) |
| greedy | Wh/run | -7.41 | [-89.06, +74.23] | 255.29 | 0.8552 (monte-carlo) | 1 | yes (+/-100) |
| hungarian | completions/100 (=pp) | +0.28 | [-0.37, +0.92] | 2.01 | 0.4396 (exact) | 1 | yes (+/-1) |
| hungarian | Wh/run | +28.37 | [-45.02, +101.77] | 229.50 | 0.438 (monte-carlo) | 1 | no (+/-100) |

## Simple effects of the energy term at each SOC level (alpha1 - alpha0; unadjusted, descriptive)

| Policy | SOC | Outcome | Mean | 95% t CI | SD | sign-flip p |
|---|---|---|---|---|---|---|
| greedy | 100% | done | +0.00 pp | [+0.00, +0.00] | 0.00 | 1 (exact) |
| greedy | 100% | bat | -48.84 Wh | [-125.57, +27.89] | 239.92 | 0.2095 (monte-carlo) |
| greedy | 100% | km | -0.60 km | [-2.37, +1.18] | 5.55 | 0.5035 (monte-carlo) |
| greedy | 100% | wait | +4.30 s | [-1.84, +10.45] | 19.22 | 0.1647 (monte-carlo) |
| greedy | 25% | done | +0.00 pp | [-0.91, +0.91] | 2.85 | 1 (exact) |
| greedy | 25% | bat | -56.25 Wh | [-111.61, -0.90] | 173.09 | 0.04595 (monte-carlo) |
| greedy | 25% | km | -1.13 km | [-2.47, +0.21] | 4.19 | 0.09724 (monte-carlo) |
| greedy | 25% | wait | +3.24 s | [-3.87, +10.35] | 22.25 | 0.3628 (monte-carlo) |
| hungarian | 100% | done | +0.00 pp | [+0.00, +0.00] | 0.00 | 1 (exact) |
| hungarian | 100% | bat | -60.10 Wh | [-120.63, +0.44] | 189.28 | 0.05164 (monte-carlo) |
| hungarian | 100% | km | -1.06 km | [-2.49, +0.37] | 4.47 | 0.1429 (monte-carlo) |
| hungarian | 100% | wait | -0.82 s | [-5.34, +3.70] | 14.13 | 0.7167 (monte-carlo) |
| hungarian | 25% | done | +0.28 pp | [-0.37, +0.92] | 2.01 | 0.4396 (exact) |
| hungarian | 25% | bat | -31.72 Wh | [-101.01, +37.56] | 216.65 | 0.3574 (monte-carlo) |
| hungarian | 25% | km | -0.50 km | [-2.12, +1.12] | 5.07 | 0.5354 (monte-carlo) |
| hungarian | 25% | wait | +4.31 s | [-1.45, +10.06] | 18.00 | 0.138 (monte-carlo) |

## Energy, service and energy per completed request reported together (sums over seeds)

| Policy | SOC | alpha | Completed | Fulfil % | Battery Wh/run | Wh per completion | 95% paired-bootstrap CI of ratio change (a1 vs a0) |
|---|---|---|---|---|---|---|---|
| greedy | 100% | 0 | 4000/4000 | 100.00 | 5844.8 | 58.45 |  |
| greedy | 100% | 1 | 4000/4000 | 100.00 | 5795.9 | 57.96 | [-1.23, +0.25] Wh |
| greedy | 25% | 0 | 3902/4000 | 97.55 | 6040.5 | 61.92 |  |
| greedy | 25% | 1 | 3902/4000 | 97.55 | 5984.2 | 61.35 | [-1.39, +0.24] Wh |
| hungarian | 100% | 0 | 4000/4000 | 100.00 | 5841.2 | 58.41 |  |
| hungarian | 100% | 1 | 4000/4000 | 100.00 | 5781.1 | 57.81 | [-1.17, -0.03] Wh |
| hungarian | 25% | 0 | 3904/4000 | 97.60 | 6006.8 | 61.54 |  |
| hungarian | 25% | 1 | 3915/4000 | 97.88 | 5975.1 | 61.05 | [-1.29, +0.28] Wh |

Per-seed differences written to paired_differences_by_seed.csv
