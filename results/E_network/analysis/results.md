# Experiment E — validation and results

640 validated runs, 40 paired seeds.
PASS: frozen source, both fixed inputs, mapped depot nodes, settings, canonical hashes, mapped OD identities, arrival compression, fleet, completion and battery accounting.
Pilot excluded from inference. Positive savings denote lower withdrawal; interactions are percentage-point differences.

| Contrast | Mean pp | 95% CI | Holm p | Service guard |
|---|---:|---:|---:|---|
| UTP / 1800 s / greedy | 1.211 | [0.205, 2.217] | 0.1579 | met |
| UTP / 1800 s / hungarian | 1.578 | [0.182, 2.974] | 0.201 | met |
| UTP / 600 s / greedy | -0.733 | [-2.071, 0.605] | 0.8184 | met |
| UTP / 600 s / hungarian | -1.009 | [-2.563, 0.546] | 0.796 | met |
| UM_district / 1800 s / greedy | -0.368 | [-1.729, 0.993] | 1 | met |
| UM_district / 1800 s / hungarian | -0.234 | [-1.654, 1.187] | 1 | met |
| UM_district / 600 s / greedy | -1.281 | [-2.890, 0.328] | 0.5698 | met |
| UM_district / 600 s / hungarian | -1.547 | [-3.227, 0.133] | 0.4195 | met |
| UM minus UTP / 1800 s / greedy | -1.579 | [-3.304, 0.145] | 0.4348 | — |
| UM minus UTP / 1800 s / hungarian | -1.811 | [-3.809, 0.187] | 0.4348 | — |
| UM minus UTP / 600 s / greedy | -0.548 | [-2.627, 1.531] | 1 | — |
| UM minus UTP / 600 s / hungarian | -0.538 | [-3.099, 2.022] | 1 | — |
| 600 minus 1800 / UTP / greedy | -1.944 | [-3.713, -0.175] | 0.2288 | — |
| 600 minus 1800 / UTP / hungarian | -2.586 | [-4.809, -0.364] | 0.1904 | — |
| 600 minus 1800 / UM_district / greedy | -0.913 | [-2.793, 0.967] | 1 | — |
| 600 minus 1800 / UM_district / hungarian | -1.313 | [-3.674, 1.048] | 1 | — |

The completion guard is descriptive, not a multiplicity-adjusted noninferiority test. No energy-benefit claim for a cell failing the guard.

Different real OSM geometry with synthetic mapped demand and depot locations, not observed UM demand or evidence of legal deployability. Same frozen undirected flat-road physics and dispatch policies. No third policy; no tuning based on pilot or confirmation. Pilot seed excluded from inference.
