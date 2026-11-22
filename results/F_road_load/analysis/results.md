# Experiment F — validation and results

960 validated runs, 40 paired seeds.
PASS: frozen source, fixed UTP inputs, depot nodes, settings, canonical hashes, workload, fleet, completion and battery accounting.
Pilot excluded from inference. Positive savings denote lower withdrawal; interactions are percentage-point differences.

| Contrast | Mean pp | 95% CI | Holm p | Service guard |
|---|---:|---:|---:|---|
| LOW / SOC 100% / greedy | 1.922 | [0.638, 3.206] | 0.04 | met |
| LOW / SOC 100% / hungarian | 1.520 | [0.164, 2.877] | 0.2253 | met |
| LOW / SOC 25% / greedy | 1.139 | [-0.141, 2.419] | 0.3978 | met |
| LOW / SOC 25% / hungarian | 0.462 | [-0.735, 1.659] | 0.8818 | met |
| BASE / SOC 100% / greedy | 2.572 | [1.106, 4.039] | 0.01078 | met |
| BASE / SOC 100% / hungarian | 1.639 | [0.187, 3.091] | 0.2253 | met |
| BASE / SOC 25% / greedy | 1.428 | [0.082, 2.774] | 0.2348 | met |
| BASE / SOC 25% / hungarian | 1.033 | [-0.158, 2.223] | 0.3978 | met |
| HIGH / SOC 100% / greedy | 2.998 | [1.676, 4.321] | 0.00084 | met |
| HIGH / SOC 100% / hungarian | 1.785 | [0.378, 3.191] | 0.1287 | met |
| HIGH / SOC 25% / greedy | -0.183 | [-1.014, 0.647] | 0.8818 | met |
| HIGH / SOC 25% / hungarian | -0.419 | [-1.145, 0.307] | 0.7538 | met |
| LOW minus BASE / SOC 100% / greedy | -0.651 | [-1.809, 0.507] | 1 | — |
| LOW minus BASE / SOC 100% / hungarian | -0.119 | [-1.141, 0.903] | 1 | — |
| LOW minus BASE / SOC 25% / greedy | -0.289 | [-2.089, 1.511] | 1 | — |
| LOW minus BASE / SOC 25% / hungarian | -0.571 | [-1.973, 0.832] | 1 | — |
| HIGH minus BASE / SOC 100% / greedy | 0.426 | [-1.240, 2.091] | 1 | — |
| HIGH minus BASE / SOC 100% / hungarian | 0.146 | [-1.070, 1.361] | 1 | — |
| HIGH minus BASE / SOC 25% / greedy | -1.611 | [-3.453, 0.230] | 0.9358 | — |
| HIGH minus BASE / SOC 25% / hungarian | -1.452 | [-2.904, 0.001] | 0.6024 | — |
| 25% minus 100% / LOW / greedy | -0.783 | [-1.984, 0.419] | 1 | — |
| 25% minus 100% / LOW / hungarian | -1.058 | [-2.315, 0.198] | 0.9589 | — |
| 25% minus 100% / BASE / greedy | -1.144 | [-3.057, 0.769] | 1 | — |
| 25% minus 100% / BASE / hungarian | -0.606 | [-2.495, 1.282] | 1 | — |
| 25% minus 100% / HIGH / greedy | -3.182 | [-4.702, -1.661] | 0.00224 | — |
| 25% minus 100% / HIGH / hungarian | -2.204 | [-3.697, -0.710] | 0.07488 | — |

The completion guard is descriptive, not a multiplicity-adjusted noninferiority test. No energy-benefit claim for a cell failing the guard.

External cargo vehicle diagnostic informs an effective rolling-resistance sensitivity range, not physical estimates for the target GMTLSV nor a confidence interval. Selected near-flat slow winter measurements are DC-link gross positive draw, not pack-wide battery discharge. The holdout check does not establish accurate transportability; two of four holdout effective coefficients are just outside the training-derived range. All other cart physics, SOC reserve and charging are unchanged. No tuning on confirmatory simulation outcomes.
