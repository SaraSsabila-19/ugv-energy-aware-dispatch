# Computational requirements

Measured on the kit author's 2-core cloud VM (CPython 3.13, recorded package versions), probe enabled. Each simulation is single-threaded, so wall time scales with the number of parallel jobs up to your physical core count. A modern desktop core is typically 0.5–1.0× these per-run times.

| Run type | Wall time per run | Disk per run |
| --- | --- | --- |
| 12 UGVs / 100 requests | about 10–11 s | about 2.1 MB |
| 24 UGVs / 100 requests | about 11–12 s | about 2.2 MB |
| 24 UGVs / 200 requests | about 19–20 s | about 2.4 MB |

| Campaign | Runs | Core-hours | Wall time, 4 jobs | Wall time, 8 jobs | Disk |
| --- | --- | --- | --- | --- | --- |
| Self-test (`tests/selftest.sh`) | 4 (+4 forced failures) | under 0.1 | about 1 min | about 1 min | 10 MB |
| Smoke and regression (`01_...`) | 38 | about 0.12 | about 2–3 min | about 1–2 min | 90 MB |
| Experiment B | 960 | about 3.8 | about 1 h | about 30 min | about 2.3 GB |
| Experiment A | 2,000 | about 6.1 | about 1.5 h | about 46 min | about 4.9 GB |

Memory is about 300 MB per parallel run. Exports (compact zip) are about 10–20% of the campaign size. `--full` additionally tars every run folder.

`bin/matrix.py --protocol ... --campaign ... --jobs N` prints the remaining estimate at any time.
