# Validation: EXP_B_FLEET

Runs expected 960, validated 960, missing 0, failed 0.

| Check | Status | Details |
| --- | --- | --- |
| completeness | PASS |  |
| source | PASS |  |
| overrides | PASS |  |
| settings | PASS |  |
| workload | PASS |  |
| fleet | PASS |  |
| accounting | PASS |  |
| probe | FAIL | EXP_B_FLEET__V12R100__M825_P80__greedy__soc25__a0__seed704001: planned energy 6048.2 vs battery 6108.0 differ >0.5%; EXP_B_FLEET__V12R100__M825_P80__greedy__soc25__a0__seed731001: planned energy 5668.3 vs battery 5738.3 differ >0.5%; EXP_B_FLEET__V24R200__M825_P80__greedy__soc25__a0__seed717001: planned energy 11289.7 vs battery 11468.4 differ >0.5% |
| cost_change | PASS |  |
| blocking | PASS |  |

Overall: **FAIL**