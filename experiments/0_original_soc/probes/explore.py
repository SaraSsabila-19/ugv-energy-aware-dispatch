"""Exploratory probes: arrival surge (600 s) and energy-only objective (beta=0).
usage: python explore.py"""
import csv, glob, os, math, collections
import numpy as np
from scipy import stats
def load(pattern):
    R = {}
    for f in glob.glob(pattern):
        rd = os.path.dirname(f)
        if not os.path.exists(os.path.join(os.path.dirname(os.path.dirname(rd)), "DONE")): continue
        r = next(csv.DictReader(open(f)))
        rr = list(csv.DictReader(open(rd + '/request_results.csv')))
        pkm = sum(float(x['passenger_distance_km'] or 0) for x in rr if x['request_completed'] == '1')
        k = (r['algorithm'], float(r['initial_soc_low']), float(r['alpha_energy']), float(r['beta_time']), int(r['trial_seed']))
        R[k] = dict(done=int(r['completed_requests']), bat=float(r['total_battery_withdrawn_Wh']), km=float(r['total_distance_km']),
                    pool=pkm / float(r['total_distance_km']), wait=float(r['mean_deadline_limited_pickup_wait_s']))
    return R
def tci(d):
    d = np.asarray(d, float); n = len(d); m = d.mean(); h = stats.t.ppf(.975, n - 1) * d.std(ddof=1) / math.sqrt(n); return m, m - h, m + h
def report(R, label, base, alt):
    algs = sorted({k[0] for k in R}); seeds = sorted({k[4] for k in R})
    print(f'\n=== {label}: {len(seeds)} seeds ===')
    for a in algs:
        for soc in (1.0, 0.25):
            ks = [s for s in seeds if (a, soc) + base + (s,) in R and (a, soc) + alt + (s,) in R]
            if not ks: continue
            B = [R[(a, soc) + base + (s,)] for s in ks]; A = [R[(a, soc) + alt + (s,)] for s in ks]
            db = [x['bat'] - y['bat'] for x, y in zip(A, B)]; dd = [x['done'] - y['done'] for x, y in zip(A, B)]
            dw = [x['wait'] - y['wait'] for x, y in zip(A, B)]
            mb = np.mean([y['bat'] for y in B])
            m1, l1, h1 = tci(db); m2, l2, h2 = tci(dd); m3, l3, h3 = tci(dw)
            whc = lambda X: sum(x['bat'] for x in X) / sum(x['done'] for x in X)
            print(f"{a:9s} SOC {soc:4}: base done {sum(y['done'] for y in B)}/{100*len(ks)}, alt done {sum(x['done'] for x in A)}; "
                  f"pooling (pass-km/veh-km) {np.mean([y['pool'] for y in B]):.2f}; "
                  f"D battery {m1:+.1f} Wh [{l1:+.1f},{h1:+.1f}] = {100*m1/mb:+.2f}%; D done {m2:+.2f} [{l2:+.2f},{h2:+.2f}]; D wait {m3:+.1f} s [{l3:+.1f},{h3:+.1f}]; "
                  f"Wh/compl {whc(B):.2f} -> {whc(A):.2f}")
S = load('/home/claude/surge_out/*/results/*/run_summary.csv')
report(S, 'Arrival surge, 100 requests in 600 s (alpha 1 vs 0)', (0.0, 1.0), (1.0, 1.0))
C = load('/home/claude/conf_out/*/results/*/run_summary.csv')
Bt = load('/home/claude/beta_out/*/results/*/run_summary.csv')
seeds_b = sorted({k[4] for k in Bt})
CB = {k: v for k, v in C.items() if k[4] in seeds_b}; CB.update(Bt)
report(CB, 'Energy-only objective: (alpha 1, beta 0) vs time-only (alpha 0, beta 1)', (0.0, 1.0), (1.0, 0.0))
report(CB, 'Same seeds, confirmatory contrast: (alpha 1, beta 1) vs (alpha 0, beta 1)', (0.0, 1.0), (1.0, 1.0))
if C:
    print('\nBaseline (1,800 s arrivals) pooling ratio, confirmatory runs:',
          {f'{a} {soc}': round(np.mean([v['pool'] for k, v in C.items() if k[0] == a and k[1] == soc]), 2) for a in ('hungarian', 'greedy') for soc in (1.0, 0.25)})
