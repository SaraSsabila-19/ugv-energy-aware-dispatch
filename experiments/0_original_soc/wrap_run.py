# Runs frozen app.py headless with extra trial seeds appended in memory (app.py on disk unchanged).
# usage: python wrap_run.py EXTRA_SEEDS_CSV -- <app.py headless args>
import sys, os
sys.path.insert(0, os.getcwd())
extra = [int(x) for x in sys.argv[1].split(',') if x]
assert sys.argv[2] == '--'
sys.argv = ['app.py'] + sys.argv[3:]
import app
for s in extra:
    if s not in app.TRIAL_SEEDS: app.TRIAL_SEEDS.append(s)
raise SystemExit(app.headless_main())
