"""Mechanism analysis of the energy-weight x SOC experiment. usage: python mechanism.py OUT_ROOT"""
import csv, glob, os, sys, math, collections, json
import numpy as np
from scipy import stats
out = sys.argv[1]
R = {}
for f in glob.glob(os.path.join(out, '*', 'results', '*', 'run_summary.csv')):
    rd = os.path.dirname(f); r = next(csv.DictReader(open(f)))
    k = (r['algorithm'], float(r['initial_soc_low']), int(float(r['alpha_energy'])), int(r['trial_seed']))
    rr = list(csv.DictReader(open(rd + '/request_results.csv')))
    wd = {x['request_id']: x for x in csv.DictReader(open(rd + '/request_wait_diagnostics.csv'))}
    cd = list(csv.DictReader(open(rd + '/cost_diagnostics.csv')))
    E = T = C = 0.0
    for x in cd:
        if int(x['within_request_dof'] or 0) > 0 and float(x['within_request_energy_ss']) > 0 and float(x['within_request_time_ss']) > 0:
            E += float(x['within_request_energy_ss']); T += float(x['within_request_time_ss']); C += float(x['within_request_cross_sum'])
    fails = [x for x in rr if x['request_completed'] != '1']
    R[k] = dict(done=int(r['completed_requests']), bat=float(r['total_battery_withdrawn_Wh']), km=float(r['total_distance_km']),
                drv=float(r['driving_Wh']), dwell=float(r['dwell_Wh']), park=float(r['battery_parked_Wh']),
                chg=float(r['total_energy_charged_Wh']), grid=float(r['total_grid_import_Wh']),
                wait=float(r['mean_deadline_limited_pickup_wait_s']), dur=float(r['simulation_duration_s']),
                E=E, T=T, C=C,
                fails={x['request_id'] for x in fails},
                fail_reasons=collections.Counter(x['failure_reason'] for x in fails),
                fail_times=[float(x['created_time_s']) for x in fails],
                fail_all_blocked=sum(1 for x in fails if wd[x['request_id']]['had_feasible_pair'] == '0' and wd[x['request_id']]['had_energy_blocked_pair'] == '1'),
                minsoc=float(r['minimum_fleet_SOC_Wh']))
algs = sorted({k[0] for k in R}); seeds = sorted({k[3] for k in R}); n = len(seeds)
print(f'{len(R)} runs, {n} seeds\n')
def tci(d):
    d = np.asarray(d, float); m = d.mean(); h = stats.t.ppf(.975, n - 1) * d.std(ddof=1) / math.sqrt(n); return m, m - h, m + h
def sf(d):
    d = np.asarray(d, float); obs = abs(d.sum()); rng = np.random.default_rng(1)
    e = rng.choice([-1.0, 1.0], size=(400000, n)); return (np.sum(np.abs(e @ d) >= obs - 1e-9) + 1) / 400001
print('== 1. Condition means (per run) ==')
print('alg soc a | done | bat Wh | driving | dwell | parked | km | Wh/km | charged Wh | grid Wh | sim dur s | wait s')
for a in algs:
    for soc in (1.0, 0.25):
        for x in (0, 1):
            v = [R[(a, soc, x, s)] for s in seeds]
            mean = lambda key: np.mean([q[key] for q in v])
            print(f"{a} {soc} {x} | {sum(q['done'] for q in v)} | {mean('bat'):.1f} | {mean('drv'):.1f} | {mean('dwell'):.1f} | {mean('park'):.1f} | {mean('km'):.2f} | {sum(q['drv'] for q in v)/sum(q['km'] for q in v):.2f} | {mean('chg'):.1f} | {mean('grid'):.1f} | {mean('dur'):.0f} | {mean('wait'):.2f}")
print('\n== 2. Simple effects of alpha (a1-a0), with Monte Carlo sign-flip p (unadjusted) ==')
for a in algs:
    for soc in (1.0, 0.25):
        for key in ('bat', 'km', 'drv', 'wait', 'done', 'dur', 'chg'):
            d = [R[(a, soc, 1, s)][key] - R[(a, soc, 0, s)][key] for s in seeds]
            m, lo, hi = tci(d); print(f'{a:9s} {soc:4} {key:5s} mean {m:+9.3f} CI [{lo:+.3f}, {hi:+.3f}] sd {np.std(d, ddof=1):8.3f} p {sf(d):.4f}')
print('\n== 3. Energy saving explained by distance: regress D_bat on D_km across seeds ==')
for a in algs:
    for soc in (1.0, 0.25):
        db = np.array([R[(a, soc, 1, s)]['bat'] - R[(a, soc, 0, s)]['bat'] for s in seeds]); dk = np.array([R[(a, soc, 1, s)]['km'] - R[(a, soc, 0, s)]['km'] for s in seeds])
        lr = stats.linregress(dk, db); print(f'{a} {soc}: slope {lr.slope:.1f} Wh/km, intercept {lr.intercept:+.1f} Wh, R^2 {lr.rvalue**2:.3f}')
print('\n== 4. Pooled within-request energy-duration correlation (cost diagnostics) ==')
for a in algs:
    for soc in (1.0, 0.25):
        for x in (0, 1):
            E = sum(R[(a, soc, x, s)]['E'] for s in seeds); T = sum(R[(a, soc, x, s)]['T'] for s in seeds); C = sum(R[(a, soc, x, s)]['C'] for s in seeds)
            print(f'{a} {soc} a{x}: r = {C / math.sqrt(E * T):.4f}')
E = sum(v['E'] for v in R.values()); T = sum(v['T'] for v in R.values()); C = sum(v['C'] for v in R.values()); print(f'ALL 320: r = {C/math.sqrt(E*T):.4f}')
print('\n== 5. Failures at 25% SOC ==')
for a in algs:
    for x in (0, 1):
        v = [R[(a, 0.25, x, s)] for s in seeds]; reasons = sum((q['fail_reasons'] for q in v), collections.Counter())
        ft = [t for q in v for t in q['fail_times']]; nf = sum(len(q['fails']) for q in v)
        print(f'{a} a{x}: {nf} failures; reasons {dict(reasons)}; all-candidates-energy-blocked {sum(q["fail_all_blocked"] for q in v)}; created-time median {np.median(ft):.0f} s, 10th pct {np.percentile(ft,10):.0f} s; seeds with any failure {sum(1 for q in v if q["fails"])}/{n}')
    ov = []; same = 0
    for s in seeds:
        A = R[(a, 0.25, 0, s)]['fails']; B = R[(a, 0.25, 1, s)]['fails']
        if A or B: ov.append(len(A & B) / len(A | B))
        if A == B: same += 1
    print(f'  {a}: seeds with identical failed-request sets a0 vs a1: {same}/{n}; mean Jaccard overlap where any fail: {np.mean(ov):.2f}')
print('\n== 6. Energy budget at 25% SOC ==')
for a in algs:
    for x in (0, 1):
        v = [R[(a, 0.25, x, s)] for s in seeds]
        print(f"{a} a{x}: withdrawal {np.mean([q['bat'] for q in v]):.0f} Wh vs initial above-reserve 5400 Wh; charged {np.mean([q['chg'] for q in v]):.0f} Wh; min fleet SOC {np.mean([q['minsoc'] for q in v]):.0f} Wh")
stored_w = (1500 - 50) * 0.85
print(f'stored charging power per idle vehicle: {stored_w:.1f} W')
for a in algs:
    for soc in (1.0, 0.25):
        d = np.mean([R[(a, soc, 0, s)]['bat'] - R[(a, soc, 1, s)]['bat'] for s in seeds])
        print(f'{a} {soc}: mean fleet saving {d:.1f} Wh/run = {d/12:.2f} Wh/vehicle = {d/12/stored_w*3600:.1f} s of depot charging per vehicle')
print('\n== 7. Per-seed spread vs mean effect (battery) ==')
for a in algs:
    for soc in (1.0, 0.25):
        d = np.array([R[(a, soc, 1, s)]['bat'] - R[(a, soc, 0, s)]['bat'] for s in seeds])
        print(f'{a} {soc}: mean {d.mean():+.1f}, sd {d.std(ddof=1):.1f}, seeds saving {int((d<0).sum())}/{n}, range [{d.min():+.0f}, {d.max():+.0f}]')
json.dump({f'{k[0]}|{k[1]}|{k[2]}|{k[3]}': {kk: vv for kk, vv in v.items() if kk not in ('fails', 'fail_reasons', 'fail_times')} for k, v in R.items()}, open('/home/claude/work/conf_runs.json', 'w'))
