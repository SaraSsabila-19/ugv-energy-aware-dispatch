#!/usr/bin/env python3
"""Frozen, resumable Experiment D: physical equivalence and alpha sweep."""
import argparse
import fcntl
import math
import shutil
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import campaign_support as S
from ugvkit import FROZEN_APP_SHA256
from ugvkit.common import BASE_CLI, BASE_ENV, load_json, write_json, seeds_from, repo_paths, sha256_file, sha256_json
from ugvkit.d_runner import coefficients

ROOT=S.ROOT
require=S.require


def protocol(pilot):
    return load_json(ROOT/'protocols'/('pilot_D.json' if pilot else 'experiment_D.json'))


def matrix(p):
    arms=dict(p['arms'])
    if p['pilot']: arms.update(control_e0=0,control_e1=1)
    result=[]
    for seed in seeds_from(p['seeds']):
        for mass,(m,mp) in p['mass_configs'].items():
            for alg in p['algorithms']:
                for arm,alpha in arms.items():
                    result.append(dict(label=f'D__{mass}__{alg}__{arm}__seed{seed}',protocol_id=p['protocol_id'],seed=seed,
                        fleet_config='V12R100',vehicles=12,requests=100,mass_config=mass,empty_mass=m,passenger_mass=mp,
                        algorithm=alg,initial_soc=1.0,alpha_energy=float(alpha),beta_time=1.0,soc_cost_weight=0.0,
                        overrides={} if mass=='M825_P80' else dict(UGV_EMPTY_MASS_KG=m,UGV_MASS_KG=m,UGV_PASSENGER_MASS_KG=mp),
                        probe=dict(enabled=not arm.startswith('control_'),alpha_alt=0),cli=dict(BASE_CLI),env=dict(BASE_ENV),arm=arm))
    require(len(result)==(36 if p['pilot'] else 1120),'Unexpected protocol design count')
    return result


def summarize(d):
    sp=d['spec']; t=d['trace']; pr=d['probe']
    r=dict(label=sp['label'],seed=sp['seed'],algorithm=sp['algorithm'],mass=sp['mass_config'],arm=sp['arm'],alpha=sp['alpha_energy'],
           workload=d['workload'],semantic_sha256=d['semantic'],**d['metrics'])
    extra=dict(rounds=0,unequal_rounds=0,action_disagreement_pct=None,matching_disagreement_pct=None,pair_insertion_disagreement_pct=None,
               local_energy_gap_pct=None,local_time_gap_s=None,native_objective_regret_per_equal_round=None,residual_bound_per_equal_round=None,candidate_count=0,residual_mae_Wh=None,residual_rmse_Wh=None,
               residual_bias_Wh=None,residual_relative_abs_pct=None,distance_residual_mae_Wh=None,negative_proxy_candidates=0,
               e0_Wh_km=None,e1_Wh_passenger_km=None,kappa_Wh_s=None,lambda_s_passenger_km=None)
    if pr is not None:
        expected=coefficients(SimpleNamespace(UGV_V_MAX=22/3.6,UGV_G=9.81,UGV_C_RR=.012,UGV_RHO=1.23,UGV_C_D=.50,UGV_A=2.,UGV_ETA=.90,UGV_DRIVING_AUX_POWER_W=50.,UGV_EMPTY_MASS_KG=sp['empty_mass'],UGV_PASSENGER_MASS_KG=sp['passenger_mass']))
        require(all(math.isclose(v,pr['coefficients'][k],rel_tol=1e-12) for k,v in expected.items()),'Coefficient mismatch')
        eq=[x for x in t if x['full_pairs']==x['proxy_pairs']]; n=pr['candidate_count']; f=math.fsum(x['full_energy_Wh'] for x in eq)
        extra.update(rounds=len(t),unequal_rounds=len(t)-len(eq),action_disagreement_pct=100*sum(not x['same_action'] for x in t)/len(t),
            matching_disagreement_pct=100*sum(not x['same_matching'] for x in t)/len(t),
            pair_insertion_disagreement_pct=100*sum(x['pair_insertion_disagreements'] for x in t)/sum(x['feasible_pairs'] for x in t),
            local_energy_gap_pct=100*math.fsum(x['full_energy_Wh']-x['proxy_energy_Wh'] for x in eq)/f if f else None,
            local_time_gap_s=math.fsum(x['full_time_s']-x['proxy_time_s'] for x in eq)/sum(x['full_pairs'] for x in eq) if sum(x['full_pairs'] for x in eq) else None,
            native_objective_regret_per_equal_round=math.fsum(x['native_objective_regret'] for x in eq)/len(eq) if eq else None,
            residual_bound_per_equal_round=math.fsum(x['residual_difference_bound'] for x in eq)/len(eq) if eq else None,
            candidate_count=n,residual_mae_Wh=pr['residual_abs_sum_Wh']/n,residual_rmse_Wh=math.sqrt(pr['residual_square_sum_Wh2']/n),
            residual_bias_Wh=pr['residual_signed_sum_Wh']/n,residual_relative_abs_pct=100*pr['residual_abs_sum_Wh']/pr['candidate_energy_abs_sum_Wh'] if pr['candidate_energy_abs_sum_Wh'] else None,
            distance_residual_mae_Wh=pr['distance_residual_abs_sum_Wh']/n,negative_proxy_candidates=pr['negative_surrogate_energy_count'],
            **{k:pr['coefficients'][k] for k in ('e0_Wh_km','e1_Wh_passenger_km','kappa_Wh_s','lambda_s_passenger_km')})
    return dict(r,**extra)


def holm(rows):
    ordered=sorted(rows,key=lambda x:x['p']); prev=0.
    for i,r in enumerate(ordered):
        prev=max(prev,min(1.,r['p']*(len(ordered)-i)));r['holm_p']=prev


def analyze(out,p,specs):
    import numpy as np
    from scipy import stats
    A=out/'analysis';A.mkdir(exist_ok=True)
    data={}; flat=[]; rr=[]; paired=[]; controls=0; work={}
    for sp in specs:
        d=S.inspect(out,sp); seed=sp['seed']; match=(d['workload'],d['fleet'])
        if seed not in work:work[seed]=match
        require(work[seed]==match,'Workload/fleet mismatch')
        key=(seed,sp['mass_config'],sp['algorithm'],sp['arm']); data[key]=summarize(d); flat.append(data[key])
        for x in d['trace']:rr.append(dict(label=sp['label'],**x))
    if p['pilot']:
        for (seed,mass,alg,arm),r in data.items():
            if arm.startswith('control_'):
                base=data[seed,mass,alg,arm[8:]]
                require(r['semantic_sha256']==base['semantic_sha256'] and all(r[k]==base[k] for k in ('battery_Wh','km','wait_s','ride_s','completed','grid_Wh','duration_s','passenger_km')),'Native instrumented/control mismatch')
                controls+=1
        require(controls==8,'Missing native controls')
    S.csvout(A/'run_level.csv',flat);S.csvout(A/'round_diagnostics.csv',rr)
    means=[]; local=[]; primary=[]; sweep=[]
    seeds=seeds_from(p['seeds'])
    metric_keys=('battery_Wh','wait_s','ride_s','completed','grid_Wh','km','passenger_km','passenger_km_per_productive_km')
    local_keys=('rounds','unequal_rounds','action_disagreement_pct','matching_disagreement_pct','pair_insertion_disagreement_pct','local_energy_gap_pct','local_time_gap_s','native_objective_regret_per_equal_round','residual_bound_per_equal_round','residual_mae_Wh','residual_rmse_Wh','residual_bias_Wh','residual_relative_abs_pct','distance_residual_mae_Wh','negative_proxy_candidates','lambda_s_passenger_km')
    def avg(rs,k):
        vals=[r[k] for r in rs if r[k] is not None]; return float(np.mean(vals)) if vals else None
    def estimates(x):
        x=np.asarray(x,dtype=float); n=len(x); m=float(np.mean(x)); se=float(np.std(x,ddof=1)/np.sqrt(n))
        h=float(stats.t.ppf(.975,n-1)*se); return m,se,m-h,m+h
    rng=np.random.default_rng(p.get('inference',{}).get('randomization_seed',52601))
    for mass in p['mass_configs']:
        for alg in p['algorithms']:
            for arm in p['arms']:
                rs=[data[s,mass,alg,arm] for s in seeds]; rec=dict(mass=mass,algorithm=alg,arm=arm,alpha=p['arms'][arm],n=len(rs),**{k:avg(rs,k) for k in metric_keys})
                rec['saving_pct_vs_e0']=float(np.mean([100*(data[s,mass,alg,'e0']['battery_Wh']-r['battery_Wh'])/data[s,mass,alg,'e0']['battery_Wh'] for s,r in zip(seeds,rs)]));means.append(rec)
                if arm=='e1':local.append(dict(mass=mass,algorithm=alg,n=len(rs),**{k:avg(rs,k) for k in local_keys}))
                for ref in ('e0','e1'):
                    if ref==arm:continue
                    ds=[]
                    for s,r in zip(seeds,rs):
                        b=data[s,mass,alg,ref]; off=data[s,mass,alg,'e0']['battery_Wh']
                        z=dict(seed=s,mass=mass,algorithm=alg,arm=arm,reference=ref,battery_pp=100*(b['battery_Wh']-r['battery_Wh'])/off,wait_s=b['wait_s']-r['wait_s'],ride_s=b['ride_s']-r['ride_s'],completed=r['completed']-b['completed'])
                        ds.append(z);paired.append(z)
                    if p['pilot']:continue
                    for k in ('battery_pp','wait_s','ride_s','completed'):
                        x=np.array([z[k] for z in ds]); m,se,lo,hi=estimates(x)
                        sweep.append(dict(mass=mass,algorithm=alg,arm=arm,reference=ref,metric=k,mean=m,ci_low=lo,ci_high=hi,n=len(x)))
                        if ref=='e1' and arm=='pk1':
                            margin=p['margins'][k]; pv=max(stats.t.sf((m+margin)/se,len(x)-1),stats.t.cdf((m-margin)/se,len(x)-1)) if se else float(not (-margin<m<margin))
                            primary.append(dict(family='equivalence',mass=mass,algorithm=alg,arm=arm,reference=ref,metric=k,mean=m,ci_low=lo,ci_high=hi,margin=margin,p=float(pv),holm_p=0.))
                        if ref=='e0' and k=='battery_pp':
                            count=0; draws=p['inference']['randomization_draws']
                            for start in range(0,draws,5000):
                                signs=rng.integers(0,2,size=(min(5000,draws-start),len(x)))*2-1
                                count+=int(np.sum(np.abs(np.mean(signs*x,axis=1))>=abs(m)-1e-12))
                            primary.append(dict(family='energy_sweep',mass=mass,algorithm=alg,arm=arm,reference=ref,metric=k,mean=m,ci_low=lo,ci_high=hi,margin=None,p=(count+1)/(draws+1),holm_p=0.))
    S.csvout(A/'condition_means.csv',means); S.csvout(A/'same_state_e1.csv',local);S.csvout(A/'paired_seed_effects.csv',paired)
    if not p['pilot']:
        for family,n in [('equivalence',16),('energy_sweep',24)]:
            group=[r for r in primary if r['family']==family];require(len(group)==n,'Missing prespecified contrast');holm(group)
        S.csvout(A/'primary_contrasts.csv',primary);S.csvout(A/'sweep_intervals.csv',sweep)
    report=['# Experiment D — validation and results','',f"{p['protocol_id']}: {len(flat)} validated runs, {len(seeds)} paired seeds; {controls} native controls matched.",
            'PASS: frozen source/input, protocol, workload/fleet pairing, candidate count, active route energy, matching and accounting.',
            'Pilot is excluded from confirmation. Positive values: lower battery/wait/ride or higher completion. Same-state local gap is native e1 minus surrogate, descriptive.','']
    if p['pilot']: report+=['PILOT PASS — all seven arms and eight native controls verified. No confirmatory inference.']
    else:
        report+=['## Equivalence to native energy weight 1','', '| Mass | Policy | Metric | Mean | 95% CI | Holm TOST p | Equivalent |','|---|---|---|---:|---|---:|---|']
        for r in primary:
            if r['family']=='equivalence':report.append(f"| {r['mass']} | {r['algorithm']} | {r['metric']} | {r['mean']:.3f} | [{r['ci_low']:.3f}, {r['ci_high']:.3f}] | {r['holm_p']:.4g} | {'yes' if r['holm_p']<.05 else 'not established'} |")
        report+=['','## Energy sweep vs time-only','', '| Mass | Policy | Arm | Saving pp | 95% CI | Holm p |','|---|---|---|---:|---|---:|']
        for r in primary:
            if r['family']=='energy_sweep':report.append(f"| {r['mass']} | {r['algorithm']} | {r['arm']} | {r['mean']:.3f} | [{r['ci_low']:.3f}, {r['ci_high']:.3f}] | {r['holm_p']:.4g} |")
    report+=['','## Same-state proxy diagnostics (native e1 reference trajectories)','', '| Mass | Policy | Action disagreement % | Residual MAE Wh | Unequal rounds per run |','|---|---|---:|---:|---:|']
    for r in local:report.append(f"| {r['mass']} | {r['algorithm']} | {r['action_disagreement_pct']:.3f} | {r['residual_mae_Wh']:.3f} | {r['unequal_rounds']:.3f} |")
    report+=['','No claim of exact equivalence or optimal alpha follows from a high correlation. The Pareto comparison is descriptive; no selection or tuning on confirmatory seeds.']
    (A/'results.md').write_text('\n'.join(report)+'\n');print('\n'.join(report),flush=True)
    figures(A,means)
    write_json(out/'validation_report.json',dict(status='PASS',protocol_sha256=sha256_json(p),expected=len(specs),validated=len(flat),native_controls=controls,analysis_sha256=sha256_file(A/'run_level.csv')))


def figures(A,means):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    masses=sorted({r['mass'] for r in means}); algs=['greedy','hungarian']
    fig,axes=plt.subplots(2,2,figsize=(9,6),layout='constrained')
    for i,m in enumerate(masses):
        for j,alg in enumerate(algs):
            ax=axes[i,j];rs=[r for r in means if r['mass']==m and r['algorithm']==alg];native=sorted([r for r in rs if r['arm']!='pk1'],key=lambda r:r['alpha']);pk=next(r for r in rs if r['arm']=='pk1')
            ax.plot([r['alpha'] for r in native],[r['saving_pct_vs_e0'] for r in native],'-o',color='#0072B2',label='Native');ax.scatter([1],[pk['saving_pct_vs_e0']],marker='D',color='#D55E00',label='Passenger-km');ax.axhline(0,color='gray',lw=.7);ax.set(title=f'{m} / {alg}',xlabel='Energy weight',ylabel='Battery saving (%)');ax.legend(fontsize=8)
    for ext in ('png','pdf'):fig.savefig(A/f'weight_sweep.{ext}',dpi=300)
    plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(9,6),layout='constrained')
    for i,m in enumerate(masses):
        for j,alg in enumerate(algs):
            ax=axes[i,j];rs=[r for r in means if r['mass']==m and r['algorithm']==alg]
            for r in rs:
                ax.scatter(r['wait_s'],r['battery_Wh'],marker='D' if r['arm']=='pk1' else 'o',color='#D55E00' if r['arm']=='pk1' else '#0072B2');ax.annotate(r['arm'],(r['wait_s'],r['battery_Wh']),fontsize=7,xytext=(2,3),textcoords='offset points')
            ax.set(title=f'{m} / {alg}',xlabel='Mean pickup wait (s)',ylabel='Battery withdrawal (Wh)')
    for ext in ('png','pdf'):fig.savefig(A/f'energy_wait_pareto.{ext}',dpi=300)
    plt.close(fig)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['run','status','validate']);ap.add_argument('--pilot',action='store_true');ap.add_argument('--repo',default='~/ugv-benchmark-public');ap.add_argument('--out-root',default='~/ugv_v5_campaigns');ap.add_argument('--jobs',type=int,default=2);ap.add_argument('--timeout',type=int,default=3600);a=ap.parse_args()
    p=protocol(a.pilot);specs=matrix(p);base=Path(a.out_root).expanduser().resolve();out=base/('pilot_D' if a.pilot else 'experiment_D_equivalence')
    if a.action=='status':
        ok=sum((out/'runs'/s['label']/'RUN_OK.json').exists() for s in specs);bad=sum((out/'runs'/s['label']/'RUN_FAILED.json').exists() for s in specs);print(f'{ok}/{len(specs)} completion markers; {len(specs)-ok} remaining; {bad} failure markers.');return
    require(a.jobs>0,'Jobs must be positive');paths=repo_paths(a.repo);ident=S.identity(p,paths)
    require(ident['source_sha256']==FROZEN_APP_SHA256 and ident['inputs_sha256']==S.INPUT_HASHES,'Frozen source/input SHA-256 mismatch')
    if not a.pilot:
        po=base/'pilot_D'; gate=load_json(po/'validation_report.json');proof=load_json(po/'PILOT_OK.json')
        require(gate['status']=='PASS' and gate['native_controls']==8 and load_json(po/'campaign_identity.json')==S.identity(protocol(True),paths) and gate['analysis_sha256']==sha256_file(po/'analysis'/'run_level.csv') and proof['validation_sha256']==sha256_file(po/'validation_report.json') and proof['zip_sha256']==sha256_file(po/'exports'/proof['zip']),'Pilot gate not satisfied')
    out.mkdir(parents=True,exist_ok=True)
    with open(out/'.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        marker=out/'campaign_identity.json'
        if marker.exists():require(load_json(marker)==ident,'Campaign identity differs; use a new directory')
        else:
            require(not any(f.name!='.lock' for f in out.iterdir()),'Nonempty foreign campaign directory');write_json(marker,ident);write_json(out/'protocol.json',p);write_json(out/'run_matrix.json',specs)
        require(load_json(out/'protocol.json')==p and load_json(out/'run_matrix.json')==specs,'Frozen protocol or run matrix mismatch')
        if a.action=='run':
            remaining=sum(not (out/'runs'/s['label']/'RUN_OK.json').exists() for s in specs);need=remaining*3*1024**2+512*1024**2
            require(shutil.disk_usage(out).free>=need,f'Insufficient disk: need {need/1024**3:.2f} GiB')
        write_json(out/'validation_report.json',dict(status='IN_PROGRESS',protocol_sha256=sha256_json(p)))
        if a.action=='run':S.batch(out,specs,paths,a.jobs,a.timeout)
        analyze(out,p,specs);z=S.export(out,p)
        if a.pilot:write_json(out/'PILOT_OK.json',dict(validation_sha256=sha256_file(out/'validation_report.json'),zip=z.name,zip_sha256=sha256_file(z)))


if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:main()
    except KeyboardInterrupt:S.halt();print('Interrupted. Resume using the identical command.',file=sys.stderr);sys.exit(130)
    except Exception as e:print(f'STOP: {e}',file=sys.stderr);sys.exit(1)
