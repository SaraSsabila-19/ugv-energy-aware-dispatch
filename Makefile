PY ?= python3

.PHONY: verify synthesis reproduce test-kits all

verify:      ## recompute all reported statistics and check every checksum (no simulation)
	$(PY) verification/verify_repository.py

synthesis:   ## post hoc replication synthesis and forest plots -> analysis/output/
	$(PY) analysis/synthesis.py

reproduce:   ## re-execute 4 archived Experiment A runs and compare every value
	$(PY) verification/reproduce_sample_runs.py

test-kits:   ## each experiment kit's own unit tests (D's frozen-hook test runs the simulator)
	cd experiments/C_dynamics && $(PY) -m unittest discover -s tests -p 'test_*.py'
	cd experiments/D_cost_proxy && $(PY) tests/test_analysis.py && $(PY) tests/test_frozen_hooks.py ../../src/frozen/app.py
	cd experiments/E_network && $(PY) -m unittest discover -s tests -p 'test_*.py'
	cd experiments/F_road_load && $(PY) -m unittest discover -s tests -p 'test_*.py'

all: verify synthesis
