# Frozen app.py with extra seeds and an overridden arrival window (temporal demand concentration).
# The override is recorded in the run's settings snapshot (ARRIVAL_WINDOW_S). app.py on disk is unchanged.
# usage: python wrap_surge.py EXTRA_SEEDS_CSV ARRIVAL_WINDOW_S -- <app.py headless args>
import sys, os
sys.path.insert(0, os.getcwd())
extra = [int(x) for x in sys.argv[1].split(',') if x]; win = float(sys.argv[2]); assert sys.argv[3] == '--'
sys.argv = ['app.py'] + sys.argv[4:]
import app
for s in extra:
    if s not in app.TRIAL_SEEDS: app.TRIAL_SEEDS.append(s)
app.ARRIVAL_WINDOW_S = win
raise SystemExit(app.headless_main())
