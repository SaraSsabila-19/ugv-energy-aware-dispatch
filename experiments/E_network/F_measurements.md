# Experiment F — measurement acquisition and calibration decision gate

## Primary dataset

Monsalve et al., 2026, *Integrated Experimental and Physics-Based Assessment of Energy and Drivetrain Performance in a Small Utility Electric Vehicle*, Applied Sciences 16(21), 10748, https://doi.org/10.3390/app162110748 . Authors state that original data are openly available at https://repositorio.ucsc.cl/handle/25022009/13166 . Download all data and documentation from the repository and upload the original archive(s). The repository was not directly retrievable in the research browser, so the data contents have not yet been verified.

Relevant measurements: DC voltage/current, GNSS trajectories and speed, nominal/reduced tyre pressures, driver approx. 75 kg and additional payload 260.5 kg, three routes. Use only the flat route for calibration of the flat-road simulator. Uphill/downhill data are a limitation check, not fitted to the flat model. Electrical recordings and GNSS have different rates and were aligned manually in the original study; verify units, time alignment, distance, vehicle curb mass, and measurement boundary before fitting. The paper reports selected runs rather than independent replicated means, so avoid inferential overclaims.

## Independent plausibility benchmark

US DOE / NEVAmerica, 2007 GEM e6, https://avt.inl.gov/sites/default/files/pdf/nev/gem2007e6.pdf . Six seats, delivered curb mass 1878 lb = 851.85 kg (0.45359237 kg/lb), maximum-speed range test 169.6 Wh-DC/mile = 105.38 Wh/km (1.609344 km/mile). Travel speed near 25 mph is substantially higher than the frozen study's 22 km/h; vehicle drivetrain and lead-acid battery also differ. Do not compare as same-cycle, and do not confuse DC consumption with AC charging consumption. This is a vehicle-class external check, not validation of the specific GMTLSV.

## Prespecified fitting and validation approach (conditional on data availability)

1. Establish energy boundary: discharge-side DC energy from timestamped V*I integration; use independent speed/distance traces and explicit auxiliary boundary. Do not equate AC grid consumption to modeled battery withdrawal.
2. Candidate model on flat roads: E = e0*distance_km + e1*passenger_km + stop/start correction + auxiliary time term. If time-series data and mass support it, estimate physically meaningful rolling-loss and efficiency combinations, not independently unidentifiable Crr, eta, Cd and auxiliary coefficients from a single aggregate Wh/km.
3. Fit only a declared subset of flat runs; hold out independent runs or conditions, not correlated rows of the same run. If only selected individual runs are available, report descriptive cross-condition errors without claiming independent population validation. Document accuracy, MAE and relative error on held-out data and compare with frozen parameters.
4. Check practical energy-policy sensitivity in independent simulation seeds using the baseline plus a small, measurement-supported parameter range. Recompute derived power constants consistently for running/parked/dwell/charging and preserve the original energy reserve; if motion parameters change, both estimator and executed motion must use the same values.
5. Freeze all values and exact source data hashes before seeing F dispatch outcomes. Proposed base simulation design: 2 algorithms x 2 alpha weights x 2 SOC levels x 3 parameter configurations x 40 fresh seeds = 960 runs, conditional on the identifiable model and disk budget. Not a launched or frozen run matrix yet.

If the actual measured data cannot be obtained or do not support identification, report the measured source as an external plausibility benchmark and a literature-anchored sensitivity range, explicitly stating that direct validation requires a measured drive on the GMTLSV.

## Optional stronger route: measurements of the actual cart

If UTP can provide the exact vehicle and a safe, approved supervised test: fixed flat course, measured distance, drive battery-side voltage/current logging, vehicle/load mass, tyre pressure, ambient conditions, repeated empty/loaded runs, controlled speeds and repeatable stop-start pattern. Keep all raw records and calibration information. Do not modify electrical equipment or drive unsupervised; use qualified staff and university approvals. No exact cart measurements are currently available to this analysis.
