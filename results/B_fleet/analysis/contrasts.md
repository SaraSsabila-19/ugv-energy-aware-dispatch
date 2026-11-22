# Contrasts: EXP_B_FLEET

Seeds available: 40. Holm adjustment within each family.

## B_descriptive

| Contrast | n | Mean | 95% CI | SD | d_z | p (method) | Holm p | Margin | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| B7_socloss_V12R100_hungarian | 40 | -1.55 completions per 100 requests | [-2.214, -0.8864] | 2.075 | -0.747 | 1.192e-07 (exact) | 7.153e-07 |  | significant |
| B7_socloss_V24R100_hungarian | 40 | 0 completions per 100 requests | [0, 0] | 0 | nan | 1 (exact) | 1 |  | not significant |
| B7_socloss_V24R200_hungarian | 40 | -0.0875 completions per 100 requests | [-0.1589, -0.0161] | 0.2232 | -0.3919 | 0.03125 (exact) | 0.09375 |  | not significant |
| B7_socloss_V12R100_greedy | 40 | -1.8 completions per 100 requests | [-2.48, -1.12] | 2.127 | -0.8464 | 2.384e-07 (exact) | 1.192e-06 |  | significant |
| B7_socloss_V24R100_greedy | 40 | 0 completions per 100 requests | [0, 0] | 0 | nan | 1 (exact) | 1 |  | not significant |
| B7_socloss_V24R200_greedy | 40 | -0.175 completions per 100 requests | [-0.2981, -0.05193] | 0.3848 | -0.4548 | 0.003906 (exact) | 0.01562 |  | significant |

## B_energy

| Contrast | n | Mean | 95% CI | SD | d_z | p (method) | Holm p | Margin | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| B5_realized_saving_V12R100_hungarian | 40 | -3.19 pp of run energy | [-4.387, -1.994] | 3.741 | -0.8527 | 9e-06 (monte-carlo) | 3.6e-05 | 1 | effect exceeding margin |
| B5_realized_saving_V24R100_hungarian | 40 | -2.009 pp of run energy | [-3.126, -0.8921] | 3.493 | -0.5753 | 0.000907 (monte-carlo) | 0.002721 | 1 | significant; size relative to margin unresolved |
| B5_realized_saving_V24R200_hungarian | 40 | -2.484 pp of run energy | [-3.477, -1.492] | 3.102 | -0.8008 | 4e-06 (monte-carlo) | 2.4e-05 | 1 | effect exceeding margin |
| B5_realized_saving_V12R100_greedy | 40 | -1.408 pp of run energy | [-2.864, 0.04867] | 4.554 | -0.3091 | 0.05812 (monte-carlo) | 0.08524 | 1 | inconclusive |
| B5_realized_saving_V24R100_greedy | 40 | -1.397 pp of run energy | [-2.745, -0.04973] | 4.214 | -0.3316 | 0.04262 (monte-carlo) | 0.08524 | 1 | inconclusive |
| B5_realized_saving_V24R200_greedy | 40 | -2.326 pp of run energy | [-3.225, -1.426] | 2.812 | -0.827 | 5e-06 (monte-carlo) | 2.5e-05 | 1 | effect exceeding margin |

## B_mechanism

| Contrast | n | Mean | 95% CI | SD | d_z | p (method) | Holm p | Margin | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| B6_decision_saving_V12R100_hungarian | 40 | 0.4593 pp of run energy | [0.3934, 0.5253] | 0.2063 | 2.227 | 1e-06 (monte-carlo) | 8e-06 |  | significant |
| B6_decision_saving_V24R100_hungarian | 40 | 0.5037 pp of run energy | [0.4318, 0.5756] | 0.2248 | 2.24 | 1e-06 (monte-carlo) | 8e-06 |  | significant |
| B6_decision_saving_V24R200_hungarian | 40 | 0.5747 pp of run energy | [0.5224, 0.6269] | 0.1633 | 3.518 | 1e-06 (monte-carlo) | 8e-06 |  | significant |
| B8_decision_saving_fleetsize_hungarian | 40 | 0.04432 pp of run energy | [-0.01028, 0.09891] | 0.1707 | 0.2596 | 0.1091 (monte-carlo) | 0.2183 |  | not significant |
| B6_decision_saving_V12R100_greedy | 40 | 0.5192 pp of run energy | [0.2604, 0.778] | 0.8093 | 0.6416 | 0.000179 (monte-carlo) | 0.000716 |  | significant |
| B6_decision_saving_V24R100_greedy | 40 | 0.3985 pp of run energy | [0.2157, 0.5814] | 0.5717 | 0.6971 | 2.1e-05 (monte-carlo) | 0.000105 |  | significant |
| B6_decision_saving_V24R200_greedy | 40 | 0.3459 pp of run energy | [0.1328, 0.5591] | 0.6666 | 0.519 | 0.001666 (monte-carlo) | 0.004998 |  | significant |
| B8_decision_saving_fleetsize_greedy | 40 | -0.1207 pp of run energy | [-0.2762, 0.03483] | 0.4863 | -0.2482 | 0.1258 (monte-carlo) | 0.2183 |  | not significant |

## B_primary

| Contrast | n | Mean | 95% CI | SD | d_z | p (method) | Holm p | Margin | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| B1_interaction_completions_V24R100_hungarian | 40 | 0 completions per 100 requests | [0, 0] | 0 | nan | 1 (exact) | 1 | 1 | no effect larger than margin |
| B1_interaction_completions_V24R200_hungarian | 40 | 0.1375 completions per 100 requests | [0.002068, 0.2729] | 0.4235 | 0.3247 | 0.06934 (exact) | 0.2773 | 1 | no effect larger than margin |
| B1_interaction_completions_V24R100_greedy | 40 | 0 completions per 100 requests | [0, 0] | 0 | nan | 1 (exact) | 1 | 1 | no effect larger than margin |
| B1_interaction_completions_V24R200_greedy | 40 | -0.05 completions per 100 requests | [-0.1634, 0.06336] | 0.3545 | -0.1411 | 0.5127 (exact) | 1 | 1 | no effect larger than margin |

## B_replication

| Contrast | n | Mean | 95% CI | SD | d_z | p (method) | Holm p | Margin | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| B2_interaction_completions_V12R100_hungarian | 40 | 0.375 completions per 100 requests | [-0.4073, 1.157] | 2.446 | 0.1533 | 0.373 (exact) | 0.7459 | 1 | inconclusive |
| B2_interaction_completions_V12R100_greedy | 40 | 0.15 completions per 100 requests | [-0.4089, 0.7089] | 1.748 | 0.08584 | 0.6542 (exact) | 0.7459 | 1 | no effect larger than margin |

## B_service_scale

| Contrast | n | Mean | 95% CI | SD | d_z | p (method) | Holm p | Margin | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| B3_socloss_fleetsize_hungarian | 40 | 1.55 completions per 100 requests | [0.8864, 2.214] | 2.075 | 0.747 | 1.192e-07 (exact) | 4.768e-07 | 1 | significant; size relative to margin unresolved |
| B4_socloss_scale_hungarian | 40 | 1.462 completions per 100 requests | [0.7974, 2.128] | 2.08 | 0.7032 | 1.788e-06 (exact) | 3.338e-06 | 1 | significant; size relative to margin unresolved |
| B3_socloss_fleetsize_greedy | 40 | 1.8 completions per 100 requests | [1.12, 2.48] | 2.127 | 0.8464 | 2.384e-07 (exact) | 7.153e-07 | 1 | effect exceeding margin |
| B4_socloss_scale_greedy | 40 | 1.625 completions per 100 requests | [0.9487, 2.301] | 2.115 | 0.7685 | 1.669e-06 (exact) | 3.338e-06 | 1 | significant; size relative to margin unresolved |
