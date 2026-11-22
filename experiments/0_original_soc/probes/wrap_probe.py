# Decision-sensitivity probe for the frozen app.py (file on disk unchanged).
# At every dispatch round it also costs each vehicle-request pair under the OTHER energy weight
# (alpha_alt) in the same fleet state, solves both matrices with the same algorithm, and records
# whether the selected matching would differ. The run itself follows the active alpha exactly.
# Side effect: pair-evaluation diagnostic counters are doubled in this run's outputs; decisions are not affected
# (verified by comparing battery/completions/distance with the uninstrumented run).
# usage: python wrap_probe.py EXTRA_SEEDS_CSV ALPHA_ALT -- <app.py headless args>
import sys, os, json, math
sys.path.insert(0, os.getcwd())
extra = [int(x) for x in sys.argv[1].split(',') if x]
alpha_alt = float(sys.argv[2])
assert sys.argv[3] == '--'
sys.argv = ['app.py'] + sys.argv[4:]
import numpy as np
import app
for s in extra:
    if s not in app.TRIAL_SEEDS:
        app.TRIAL_SEEDS.append(s)

ALT = []; META = []  # alternate-alpha costs, row-major in the order the matrix loop calls pair_cost
DE, DT = [], []   # delta energy / delta time of the active plan (finite pairs only)
stats = dict(rounds=0, rounds_multi=0, rounds_differ=0, pairs_active=0, pairs_changed=0,
             rounds_card_differ=0, rows=[])
orig_pair_cost = app.SharedRideEngine.pair_cost

def patched_pair_cost(self, m, request, alpha, beta):
    c_alt, meta_alt = orig_pair_cost(self, m, request, alpha_alt, beta)
    ALT.append(c_alt)
    c, meta = orig_pair_cost(self, m, request, alpha, beta)
    META.append((meta, meta_alt, len(getattr(m, 'planned_stops', None) or [])))
    if meta is not None and math.isfinite(c):
        DE.append(meta.get('delta_energy')); DT.append(meta.get('delta_time'))
    return c, meta

app.SharedRideEngine.pair_cost = patched_pair_cost

def wrap(fn):
    def inner(C, *a, **k):
        C = np.asarray(C, float)
        alt = np.array(ALT[-C.size:], float).reshape(C.shape) if len(ALT) >= C.size else None
        metas = META[-C.size:] if len(META) >= C.size else None
        ALT.clear(); META.clear()
        pairs = fn(C, *a, **k)
        if metas is not None:
            for (i, j) in pairs:
                mt, ma, nst = metas[i * C.shape[1] + j]
                stats['sel_pairs'] = stats.get('sel_pairs', 0) + 1
                if nst and nst > 0: stats['sel_pairs_busy'] = stats.get('sel_pairs_busy', 0) + 1
                if mt is not None and ma is not None and mt['stops'] != ma['stops']:
                    stats['sel_insertion_changed'] = stats.get('sel_insertion_changed', 0) + 1
                    stats.setdefault('ins_changes', []).append([mt['delta_energy'] - ma['delta_energy'], mt['delta_time'] - ma['delta_time']])
        if alt is not None and np.isfinite(alt).any() and fn.__name__ in ('assign_hungarian', 'assign_greedy'):
            alt_pairs = fn(alt)
            s1, s2 = set(map(tuple, pairs)), set(map(tuple, alt_pairs))
            stats['rounds'] += 1
            nreq = int(np.isfinite(C).any(axis=0).sum())
            if C.shape[0] > 1 and nreq >= 1 and np.isfinite(C).sum() > 1:
                stats['rounds_multi'] += 1
            stats['pairs_active'] += len(s1)
            stats['pairs_changed'] += len(s1 - s2)
            if s1 != s2: stats['rounds_differ'] += 1
            if len(s1) != len(s2): stats['rounds_card_differ'] += 1
            stats['rows'].append([int(C.shape[0]), int(C.shape[1]), len(s1), len(s1 - s2)])
        return pairs
    inner.__name__ = fn.__name__
    return inner

for k in ('hungarian', 'greedy'):
    app.ALGO_FUNCS[k] = wrap(app.ALGO_FUNCS[k])

rc = app.headless_main()
de = np.array(DE, float); dt = np.array(DT, float)
stats['pooled_pair_r_energy_time'] = float(np.corrcoef(de, dt)[0, 1]) if len(de) > 2 else None
stats['n_finite_pairs'] = int(len(de))
json.dump(stats, open('probe_stats.json', 'w'))
raise SystemExit(rc)
