# Post hoc replication synthesis of the canonical cell

Not prespecified. Summarises the identically specified baseline cell (12 vehicles, 100 requests, standard mass, 100% SOC, 1,800 s window, UTP network, BASE road load; alpha_E 1 vs 0) across independent seed sets. Prespecified verdicts in each study are unchanged. Pooled intervals are random-effects (DerSimonian-Laird) 95% normal intervals; study intervals are 95% t intervals. MDE80 = minimum detectable effect at 80% power.

## Battery saving (%)

| Policy | Study | Seeds | Mean | 95% CI | MDE80 | z vs others |
|---|---|---:|---:|---|---:|---:|
| greedy | Original 2x2 (approx. denominator) | 40 | 0.84 | [-0.48, 2.15] | 1.82 | -1.47 |
| greedy | A (payload) | 100 | 2.49 | [1.81, 3.17] | 0.96 | +2.68 |
| greedy | B (fleet) | 40 | 1.41 | [-0.05, 2.86] | 2.02 | -0.48 |
| greedy | C (dynamics) | 40 | 0.31 | [-0.77, 1.40] | 1.50 | -2.86 |
| greedy | D (cost proxy) | 40 | 2.37 | [1.22, 3.51] | 1.58 | +1.18 |
| greedy | E (network) | 40 | 1.21 | [0.21, 2.22] | 1.39 | -1.16 |
| greedy | F (road load) | 40 | 2.57 | [1.11, 4.04] | 2.03 | +1.19 |
| hungarian | Original 2x2 (approx. denominator) | 40 | 1.03 | [-0.01, 2.07] | 1.44 | -1.43 |
| hungarian | A (payload) | 100 | 1.72 | [0.84, 2.59] | 1.23 | +0.07 |
| hungarian | B (fleet) | 40 | 3.19 | [1.99, 4.39] | 1.66 | +2.74 |
| hungarian | C (dynamics) | 40 | 1.50 | [-0.11, 3.11] | 2.23 | -0.25 |
| hungarian | D (cost proxy) | 40 | 1.26 | [0.09, 2.42] | 1.61 | -0.81 |
| hungarian | E (network) | 40 | 1.58 | [0.18, 2.97] | 1.93 | -0.17 |
| hungarian | F (road load) | 40 | 1.64 | [0.19, 3.09] | 2.01 | -0.07 |

- **greedy**, all studies: 1.62 [0.91, 2.32]; FE 1.74; Q = 17.7 (df 6, p = 0.007); I² = 66%; tau = 0.75
- **greedy**, excluding C: 1.87 [1.26, 2.48]; FE 1.97; Q = 9.5 (df 5, p = 0.092); I² = 47%; tau = 0.52
- **hungarian**, all studies: 1.70 [1.16, 2.23]; FE 1.69; Q = 8.8 (df 6, p = 0.188); I² = 31%; tau = 0.40
- **hungarian**, excluding C: 1.72 [1.11, 2.33]; FE 1.70; Q = 8.7 (df 5, p = 0.122); I² = 42%; tau = 0.49

## Ride-time reduction (s)

| Policy | Study | Seeds | Mean | 95% CI | MDE80 | z vs others |
|---|---|---:|---:|---|---:|---:|
| greedy | C (dynamics) | 40 | 12.06 | [7.46, 16.66] | 6.37 | -0.84 |
| greedy | D (cost proxy) | 40 | 15.39 | [10.65, 20.12] | 6.56 | +0.89 |
| greedy | E (network) | 40 | 14.37 | [7.51, 21.22] | 9.49 | +0.23 |
| greedy | F (road load) | 40 | 13.16 | [8.15, 18.17] | 6.94 | -0.22 |
| hungarian | C (dynamics) | 40 | 9.57 | [3.42, 15.73] | 8.52 | -0.51 |
| hungarian | D (cost proxy) | 40 | 11.43 | [6.14, 16.73] | 7.33 | +0.19 |
| hungarian | E (network) | 40 | 13.68 | [9.16, 18.20] | 6.26 | +1.45 |
| hungarian | F (road load) | 40 | 8.47 | [3.67, 13.27] | 6.65 | -1.25 |

- **greedy**, all studies: 13.64 [11.16, 16.11]; FE 13.64; Q = 1.1 (df 3, p = 0.771); I² = 0%; tau = 0.00
- **greedy**, excluding C: 14.34 [11.36, 17.32]; FE 14.34; Q = 0.4 (df 2, p = 0.807); I² = 0%; tau = 0.00
- **hungarian**, all studies: 11.00 [8.53, 13.46]; FE 11.00; Q = 2.8 (df 3, p = 0.420); I² = 0%; tau = 0.00
- **hungarian**, excluding C: 11.27 [8.19, 14.34]; FE 11.29; Q = 2.6 (df 2, p = 0.278); I² = 22%; tau = 1.27

Notes: the original 2x2 uses the condition-mean alpha_E = 0 withdrawal as denominator. Experiment C's references were verified identical to native simulator runs (verification/c_native_reference_check), so C's estimate reflects seed sampling. Ride time is not available for the original 2x2, A or B.
