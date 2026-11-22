"""Verification checks for the energy-weight x SOC experiment. usage: python check_runs.py OUT_ROOT [N_EXPECTED]
Fails loudly if workloads, initial fleets, settings, source identity or feasibility behaviour are wrong."""
import csv, glob, json, hashlib, sys, collections, os
FROZEN='7b52bb550414469937da3098f91313b366137d43bd48b8465b840a97bffeb0a0'
out=sys.argv[1]; nexp=int(sys.argv[2]) if len(sys.argv)>2 else None
R=[]; fails=[]
for d in sorted(glob.glob(os.path.join(out,'*'))):
    lab=os.path.basename(d); f=glob.glob(d+'/results/*/run_summary.csv')
    if not f: fails.append(f'{lab}: no run_summary (failed run?)'); continue
    rd=os.path.dirname(f[0]); r=next(csv.DictReader(open(f[0])))
    st=json.load(open(os.path.join(d,'stdout.txt'))) if False else None
    snap=list(csv.DictReader(open(rd+'/vehicle_soc_snapshots.csv'))); t0=snap[0]['tick']
    fleet=tuple(sorted((x['vehicle_id'],x['home_depot_id'],x['initial_SOC_Wh']) for x in snap if x['tick']==t0))
    ef=next(csv.DictReader(open(rd+'/energy_feasibility_summary.csv')))
    R.append(dict(lab=lab,seed=int(r['trial_seed']),alg=r['algorithm'],soc=float(r['initial_soc_low']),alpha=float(r['alpha_energy']),
      beta=float(r['beta_time']),gamma=float(r['soc_cost_weight']),mode=r['cost_mode'],eref=float(r['energy_reference_Wh']),tref=float(r['time_reference_s']),
      fleetn=int(r['fleet_size']),reqs=int(r['spawned_requests']),depots=r['depot_ids'],
      src=hashlib.sha256(open(rd+'/backend_source.py','rb').read()).hexdigest(),
      wl=open(rd+'/canonical_requests.sha256').read().split()[0],fleet=fleet,
      blocked=int(ef['energy_blocked_pair_evaluations']),cost=float(r['mean_assignment_cost']),
      unc=int(r['uncompleted_requests']),done=int(r['completed_requests'])))
def chk(c,msg):
    if not c: fails.append(msg)
for x in R:
    chk(x['src']==FROZEN,f"{x['lab']}: source hash {x['src'][:12]} != frozen")
    chk((x['beta'],x['gamma'],x['mode'],x['eref'],x['tref'])==(1.0,0.0,'normalized',100.0,600.0),f"{x['lab']}: cost settings {x['beta'],x['gamma'],x['mode'],x['eref'],x['tref']}")
    chk((x['fleetn'],x['reqs'],x['depots'])==(12,100,'P02;P08;P16'),f"{x['lab']}: fleet/requests/depots {x['fleetn'],x['reqs'],x['depots']}")
    chk(x['done']+x['unc']==100,f"{x['lab']}: completions+uncompleted != 100")
    chk(f"_a{int(x['alpha'])}" in x['lab'] and f"_soc{int(round(x['soc']*100))}_" in x['lab'],f"{x['lab']}: recorded alpha/SOC {x['alpha']},{x['soc']} disagree with label")
    exp_init=str(9000.0*x['soc'])
    chk(all(v[2]==exp_init for v in x['fleet']),f"{x['lab']}: initial SOC Wh not all {exp_init}")
    if x['soc']==1.0: chk(x['blocked']==0,f"{x['lab']}: energy blocking at 100% SOC ({x['blocked']})")
by=collections.defaultdict(list)
for x in R: by[x['seed']].append(x)
wls=collections.Counter()
for s,xs in by.items():
    chk(len(xs)==8,f'seed {s}: {len(xs)} of 8 conditions present')
    chk(len({x["wl"] for x in xs})==1,f'seed {s}: workload hashes differ across conditions')
    wls[xs[0]['wl']]+=1
    for soc in (1.0,0.25):
        chk(len({x['fleet'] for x in xs if x['soc']==soc})<=1,f'seed {s} SOC {soc}: initial fleets differ across alpha/policy')
    for alg in ('hungarian','greedy'):
        c={x['alpha']:x['cost'] for x in xs if x['alg']==alg and x['soc']==1.0}
        if len(c)==2: chk(c[1.0]>c[0.0],f'seed {s} {alg}: mean assignment cost did not rise when energy term switched on')
chk(all(v==1 for v in wls.values()),'two seeds share a workload hash')
low=[x for x in R if x['soc']==0.25]
for al in (0.0,1.0):
    xs=[x for x in low if x['alpha']==al]
    if xs: chk(sum(x['blocked'] for x in xs)>0,f'alpha={al} at 25% SOC: reserve rule never blocked a pair (feasibility not active?)')
if nexp is not None: chk(len(R)==nexp,f'{len(R)} runs found, expected {nexp}')
print(f'{len(R)} runs, {len(by)} seeds checked')
if fails:
    print('FAIL'); [print('  ',m) for m in fails]; sys.exit(1)
print('PASS: frozen source; one workload per seed across all 8 conditions; identical initial fleets within SOC level;'
      ' cost settings as specified; cost changes with alpha; reserve rule active at 25% for both alpha; no blocking at 100%.')
