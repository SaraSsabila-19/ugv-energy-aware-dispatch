#!/usr/bin/env python3
"""Experiment C: deterministic single-round pulses and sequential prefixes."""
import argparse
import csv
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ugvkit import FROZEN_APP_SHA256
from ugvkit.common import BASE_CLI, BASE_ENV, load_json, write_json, sha256_file, sha256_json, repo_paths, spec_hash
from ugvkit.launch import check_run
from ugvkit.probe import events_energy
from ugvkit.impulse_runner import alpha_for

ROOT = Path(__file__).resolve().parent
INPUT_HASHES = {'utp_graph.graphml': 'ebd138a83763f11172e079f40457b371be7eebcd2e3aa018aeda13d9d70114f4',
                'hotspot_locations.csv': '6a55a275f2ac18ab383d2efcd67a31250602503a62fa3c5bf2f3f504ae0b979d'}
STOP = threading.Event()
ACTIVE = set()
LOCK = threading.Lock()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def rows(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def csvout(path, data):
    require(bool(data), f'No rows for {path}')
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(data[0])); w.writeheader(); w.writerows(data)


def protocol(pilot):
    return load_json(ROOT/'protocols'/('pilot_C.json' if pilot else 'experiment_C.json'))


def spec(p, seed, policy, mode, k=0):
    return dict(label=f'C__{policy}__seed{seed}__{mode}__{k:03d}', protocol_id=p['protocol_id'], seed=seed,
                fleet_config='V12R100', vehicles=12, requests=100, mass_config='M825_P80', algorithm=policy,
                initial_soc=1.0, alpha_energy=float(mode in ('on','control_on')), beta_time=1.0, soc_cost_weight=0.0,
                overrides={}, probe={'enabled': not mode.startswith('control_'), 'alpha_alt': 0},
                cli=dict(BASE_CLI), env=dict(BASE_ENV), mode=mode, k=k)


def references(p):
    modes = ['off','on'] + (['control_off','control_on'] if p['pilot'] else [])
    return [spec(p,s,a,m) for s in p['seeds'] for a in p['algorithms'] for m in modes]


def files_hash(rd, rdres, trace=True):
    paths = [rd/'run_spec.json', rd/'overrides_and_provenance.json', rdres/'run_summary.csv',
             rdres/'request_results.csv', rdres/'vehicle_results.csv', rdres/'assignment_events.csv',
             rdres/'vehicle_soc_snapshots.csv', rdres/'cost_diagnostics.csv', rdres/'canonical_requests.sha256',
             rdres/'run_settings.json', rdres/'energy_feasibility_summary.csv', rdres/'dispatch_invocation_events.csv']
    if trace: paths.append(rd/'probe_stats.json')
    return {str(x.relative_to(rd)): sha256_file(x) for x in paths}


def inspect(out, sp, verify_hash=True):
    rd = out/'runs'/sp['label']; ok = load_json(rd/'RUN_OK.json')
    require(ok['spec_hash'] == spec_hash(sp) and load_json(rd/'run_spec.json') == sp, f'{rd.name}: spec mismatch')
    res = (rd/ok['results_dir']).resolve()
    require(res.parent == (rd/'results').resolve(), 'Results path escaped run directory')
    if verify_hash:
        require(ok['files'] == files_hash(rd,res,sp['probe']['enabled']), f'{rd.name}: recorded file hash mismatch')
        require(sha256_file(res/'backend_source.py') == FROZEN_APP_SHA256 and sha256_file(rd/'app.py') == FROZEN_APP_SHA256, 'Source mismatch')
    prov = load_json(rd/'overrides_and_provenance.json')
    require(prov['inputs_sha256'] == INPUT_HASHES and prov['app_sha256'] == FROZEN_APP_SHA256, 'Input/source provenance mismatch')
    s = rows(res/'run_summary.csv')[0]
    for field, value in {'trial_seed':sp['seed'],'fleet_size':12,'spawned_requests':100,'initial_soc_low':1,
                         'initial_soc_high':1,'alpha_energy':sp['alpha_energy'],'beta_time':1,'soc_cost_weight':0,
                         'energy_reference_Wh':100,'time_reference_s':600,'dispatch_window_s':30,
                         'dispatch_urgent_slack_s':60}.items():
        require(float(s[field]) == value, f'{rd.name}: wrong {field}')
    require(s['algorithm']==sp['algorithm'] and s['scenario']=='S4' and s['cost_mode']=='normalized' and s['depot_ids']=='P02;P08;P16','Wrong settings')
    require(int(s['completed_requests'])+int(s['uncompleted_requests'])==100,'Completion accounting')
    params = load_json(res/'run_settings.json')['parameters']
    require(float(params['UGV_EMPTY_MASS_KG'])==825 and float(params['UGV_PASSENGER_MASS_KG'])==80, 'Mass mismatch')
    # Actual vehicle distance categories, not passenger-km subtraction.
    vr = rows(res/'vehicle_results.csv'); req = rows(res/'request_results.csv')
    snap = rows(res/'vehicle_soc_snapshots.csv'); tick = snap[0]['tick']
    fleet = sorted((v['vehicle_id'],v['home_depot_id'],v['initial_SOC_Wh']) for v in snap if v['tick']==tick)
    require(len(fleet)==12 and all(float(v[2])==9000 for v in fleet),'Initial fleet mismatch')
    ev, ne = events_energy(res); bat = float(s['total_battery_withdrawn_Wh'])
    require(math.isfinite(bat) and bat>0 and abs(ev-bat)<=0.005*bat,'Simulator assignment/battery mismatch')
    trace = []
    if sp['probe']['enabled']:
        tr = load_json(rd/'probe_stats.json'); trace = tr['rounds']
        require(tr['schema']==1 and tr['mode']==sp['mode'] and tr['k']==sp['k'],'Trace metadata mismatch')
        all_diag = rows(res/'cost_diagnostics.csv')
        require(int(s['matching_round_count'])==len(all_diag),'Simulator matrix-round count mismatch')
        diag=[d for d in all_diag if int(d['feasible_pairs'])>0]
        require(len(trace)==len(diag),'Trace / eligible matrix-round count mismatch')
        require(sum(len(r['actions']) for r in trace)==ne==int(s['matching_selected_pairs_total']),'Assignment count mismatch')
        energy = math.fsum(a['energy_Wh'] for r in trace for a in r['actions'])
        require(abs(energy-ev)<=1e-9*max(abs(ev),1),'Trace/log energy mismatch')
        dispatch_times={int(d['simulation_tick']):float(d['simulation_time_s']) for d in rows(res/'dispatch_invocation_events.csv')}
        for i,(r,d) in enumerate(zip(trace,diag),1):
            require(r['round']==i and r['alpha']==alpha_for(sp['mode'],sp['k'],i),'Schedule mismatch')
            require(r['shape']==[int(d['vehicles']),int(d['requests'])],'Matrix shape mismatch')
            r['tick']=int(d['tick']); r['time_s']=dispatch_times[r['tick']]
        if sp['mode'] in ('pulse','prefix'):
            require(len(trace)>=sp['k'],'Target round not reached')
    fields = {'battery_Wh':'total_battery_withdrawn_Wh','km':'total_distance_km','wait_s':'mean_deadline_limited_pickup_wait_s',
              'ride_s':'mean_passenger_time_s','completed':'completed_requests','grid_Wh':'total_grid_import_Wh',
              'driving_Wh':'driving_Wh','dwell_Wh':'dwell_Wh','duration_s':'simulation_duration_s'}
    metrics = {k:float(s[v]) for k,v in fields.items()}
    metrics.update({k:math.fsum(float(v[c]) for v in vr) for k,c in [('empty_pickup_km','empty_pickup_distance_km'),('return_km','return_distance_km'),('productive_km','productive_distance_km')]})
    metrics['passenger_km']=math.fsum(float(r['passenger_distance_km']) for r in req if r['request_completed']=='1' and r['passenger_distance_km'])
    # Compare simulation outputs excluding run identifier; no wall-clock diagnostics are used.
    semantic = sha256_json([{k:v for k,v in r.items() if k not in ('run_id','assignment_cost')} for r in req]+[{k:v for k,v in r.items() if k!='run_id'} for r in vr])
    return {'spec':sp,'metrics':metrics,'trace':trace,'workload':(res/'canonical_requests.sha256').read_text().split()[0],
            'fleet':fleet,'semantic':semantic}


def run_one(out, sp, paths, timeout):
    if STOP.is_set(): return 'stopped'
    rd=out/'runs'/sp['label']
    if (rd/'RUN_OK.json').exists():
        try:
            inspect(out,sp); return 'skipped'
        except Exception as e:
            # Preserve even corrupt completed attempts, then rerun only that exact spec.
            print(f'Quarantining invalid {rd.name}: {e}',flush=True)
            if (rd/'run_spec.json').exists():
                require(load_json(rd/'run_spec.json')==sp,'Different spec in completed directory; refusing to touch')
    if rd.exists():
        dest=out/'_incomplete'/f'{rd.name}__{time.time_ns()}'
        dest.parent.mkdir(exist_ok=True); shutil.move(rd,dest)
    rd.mkdir(parents=True)
    for path,name in zip(paths,['app.py','utp_graph.graphml','hotspot_locations.csv']): shutil.copy2(path,rd/name)
    write_json(rd/'run_spec.json',sp)
    try:
        env=dict(os.environ,**sp['env']); env['PYTHONPATH']=str(ROOT)
        with open(rd/'stdout.txt','w') as so,open(rd/'stderr.txt','w') as se:
            with LOCK:
                if STOP.is_set(): return 'stopped'
                proc=subprocess.Popen([sys.executable,'-m','ugvkit.impulse_runner','--run-dir',str(rd)],cwd=rd,env=env,stdout=so,stderr=se,start_new_session=True)
                ACTIVE.add(proc)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL); proc.wait(); raise
            finally:
                with LOCK: ACTIVE.discard(proc)
        require(proc.returncode==0,f'Simulator exit {proc.returncode}; see {rd}/stderr.txt')
        ok, info=check_run(rd,sp); require(ok,str(info))
        res=rd/info['results_dir']
        write_json(rd/'RUN_OK.json',dict(info,spec_hash=spec_hash(sp),files=files_hash(rd,res,sp['probe']['enabled'])))
        try: inspect(out,sp)
        except Exception:
            (rd/'RUN_OK.json').unlink(); raise
        return 'ok'
    except Exception as exc:
        write_json(rd/'RUN_FAILED.json',{'error':str(exc)})
        return f'FAILED: {exc}'


def batch(out, specs, paths, jobs, timeout):
    print(f'{len(specs)} scheduled, {sum((out/"runs"/s["label"]/"RUN_OK.json").exists() for s in specs)} markers present, jobs={jobs}',flush=True)
    failed=[]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures={pool.submit(run_one,out,s,paths,timeout):s for s in specs}
        try:
            for n,f in enumerate(as_completed(futures),1):
                stat=f.result(); label=futures[f]['label']
                if stat not in ('ok','skipped'): failed.append((label,stat))
                if stat!='skipped' or n%50==0: print(f'[{n}/{len(specs)}] {stat} {label}',flush=True)
        except KeyboardInterrupt:
            halt(); pool.shutdown(wait=True,cancel_futures=True); raise
    require(not failed,f'{len(failed)} runs failed; inspect stderr and rerun identical command. First: {failed[:2]}')


def halt():
    STOP.set()
    with LOCK:
        for proc in ACTIVE:
            try: os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError: pass


def expand(out,p):
    specs=[]
    for seed in p['seeds']:
        for policy in p['algorithms']:
            for mode,ref in [('pulse','off'),('prefix','on')]:
                n=len(inspect(out,spec(p,seed,policy,ref))['trace'])
                require(0<n<=500,'Unexpected number of rounds')
                specs.extend(spec(p,seed,policy,mode,k) for k in range(1,n+1))
    return specs


def target_check(before,after,k):
    a,b=before['trace'],after['trace']
    require(a[:k-1]==b[:k-1],f'Pre-target trace mismatch at {after["spec"]["label"]}')
    r,t=a[k-1],b[k-1]
    require(all(r[f]==t[f] for f in ('state','shape','feasibility','tick')),'Target candidate state, feasibility or timing mismatch')
    require(r['alpha']==0 and t['alpha']==1,'Target weight mismatch')
    return r,t


def end_equal(a,b):
    require(a['semantic']==b['semantic'] and a['metrics']==b['metrics'],'Endpoint physical/service outputs differ')


def analyze(out,p,exp):
    import numpy as np
    from scipy import stats
    A=out/'analysis'; A.mkdir(exist_ok=True)
    seed_rows=[]; round_rows=[]; horizon_rows=[]; run_rows=[]; workload={}
    def get(s):
        d=inspect(out,s); key=s['seed']
        if key not in workload: workload[key]=(d['workload'],d['fleet'])
        require(workload[key]==(d['workload'],d['fleet']),'Workload/fleet pairing mismatch')
        run_rows.append(dict(label=s['label'],seed=key,algorithm=s['algorithm'],mode=s['mode'],k=s['k'],workload=d['workload'],
                             trace_sha256=sha256_json(d['trace']),semantic_sha256=d['semantic'],**d['metrics']))
        return d
    for seed in p['seeds']:
        for alg in p['algorithms']:
            off,on=[get(spec(p,seed,alg,m)) for m in ('off','on')]
            if p['pilot']:
                end_equal(off,get(spec(p,seed,alg,'control_off'))); end_equal(on,get(spec(p,seed,alg,'control_on')))
            B=off['metrics']['battery_Wh']; S=B-on['metrics']['battery_Wh']; prev=off
            pulses=[]; delta=[]; local=[]; residual=[]; unequal=0
            for mode,ref in [('pulse',off),('prefix',on)]:
                for k in range(1,len(ref['trace'])+1):
                    curr=get(spec(p,seed,alg,mode,k)); before=off if mode=='pulse' else prev
                    r,t=target_check(before,curr,k)
                    glob=before['metrics']['battery_Wh']-curr['metrics']['battery_Wh']
                    matched=len(r['actions'])==len(t['actions'])
                    direct=sum(x['energy_Wh'] for x in r['actions'])-sum(x['energy_Wh'] for x in t['actions']) if matched else None
                    unchanged=r['actions']==t['actions']
                    if unchanged: end_equal(before,curr)
                    rr=dict(seed=seed,algorithm=alg,mode=mode,k=k,tick=r['tick'],time_s=r['time_s'],
                            cardinality_off=len(r['actions']),cardinality_on=len(t['actions']),matched=matched,unchanged=unchanged,
                            state_sha256=r['state'],feasibility_sha256=r['feasibility'],matrix_off_sha256=r['matrix'],matrix_on_sha256=t['matrix'],
                            global_Wh=glob,local_Wh=direct if matched else '',continuation_Wh=glob-direct if matched else '',
                            global_pct=100*glob/B,local_pct=100*direct/B if matched else '')
                    for metric in ('km','empty_pickup_km','return_km','productive_km','passenger_km','wait_s','ride_s','completed','grid_Wh'):
                        rr['delta_'+metric]=before['metrics'][metric]-curr['metrics'][metric]
                    round_rows.append(rr)
                    # Accumulated route commitments after the intervention, NOT instantaneous energy consumption.
                    # Round ordinal is used only to discard the shared history; elapsed time then aligns trajectories.
                    for horizon in (0,30,60,120,300,600,900,1800,None):
                        def accumulate(d):
                            return math.fsum(a['energy_Wh'] for q in d['trace'][k-1:]
                                             if horizon is None or q['time_s']<=r['time_s']+horizon+1e-9 for a in q['actions'])
                        hsave=accumulate(before)-accumulate(curr)
                        horizon_rows.append(dict(seed=seed,algorithm=alg,mode=mode,k=k,horizon_s='terminal' if horizon is None else horizon,
                                                 planned_saving_Wh=hsave,planned_saving_pct=100*hsave/B,matched=matched))
                    if mode=='pulse': pulses.append(glob)
                    else:
                        delta.append(glob); prev=curr
                        if matched: local.append(direct); residual.append(glob-direct)
                        else: unequal+=1
                if mode=='prefix':
                    end_equal(prev,on); require(prev['trace']==on['trace'],'All-on prefix endpoint trace mismatch')
            require(abs(math.fsum(delta)-S)<1e-7,'Prefix telescoping failed')
            row=dict(seed=seed,algorithm=alg,off_Wh=B,on_Wh=on['metrics']['battery_Wh'],whole_pct=100*S/B,
                     pulse_sum_pct=100*math.fsum(pulses)/B,nonadditivity_pct=100*(S-math.fsum(pulses))/B,
                     prefix_direct_pct=100*math.fsum(local)/B,prefix_continuation_pct=100*math.fsum(residual)/B,
                     prefix_rounds=len(delta),pulse_rounds=len(pulses),prefix_unequal=unequal)
            for metric in ('km','empty_pickup_km','return_km','productive_km','passenger_km','wait_s','ride_s','completed','grid_Wh'):
                row['off_minus_on_'+metric]=off['metrics'][metric]-on['metrics'][metric]
            seed_rows.append(row)
    require(len(set(v[0] for v in workload.values()))==len(workload),'Workloads shared across distinct seeds')
    csvout(A/'seed_effects.csv',seed_rows); csvout(A/'round_effects.csv',round_rows); csvout(A/'run_level.csv',run_rows)
    csvout(A/'response_horizons.csv',horizon_rows)
    tests=[]; rng=np.random.default_rng(469178)
    for alg in p['algorithms']:
        for field in ('whole_pct','nonadditivity_pct','prefix_continuation_pct'):
            x=np.array([r[field] for r in seed_rows if r['algorithm']==alg]); n=len(x); m=float(x.mean())
            if n>1:
                sd=float(x.std(ddof=1)); half=float(stats.t.ppf(.975,n-1)*sd/math.sqrt(n)); hits=0; obs=abs(x.sum())
                for _ in range(100):
                    signs=rng.integers(0,2,size=(10000,n),dtype=np.int8)*2-1
                    hits+=int(np.sum(np.abs(signs@x)>=obs-1e-10))
                pv=(hits+1)/1000001
                lo=m-half; hi=m+half
            else: sd=lo=hi=pv=None
            tests.append(dict(algorithm=alg,estimand=field,n=n,mean=m,sd=sd,ci_low=lo,ci_high=hi,p=pv,holm_p=None,margin_verdict='pilot only' if n==1 else ('within ±1 pp' if lo>=-1 and hi<=1 else 'outside ±1 pp' if lo>1 or hi<-1 else 'inconclusive')))
    last=0
    for i,t in enumerate(sorted((t for t in tests if t['p'] is not None),key=lambda t:t['p'])):
        last=max(last,min(1,t['p']*(len(tests)-i))); t['holm_p']=last
    csvout(A/'primary_contrasts.csv',tests)
    report=['# Experiment C — validation and results','',f'Protocol: {p["protocol_id"]}; {len(run_rows)} validated runs; {len(p["seeds"])} seeds; {len(round_rows)} target comparisons.',
            'PASS: source/input identity, matched workloads/fleets, schedule, trace accounting, pre-target equality, target candidate state, no-op checks, prefix endpoint and telescoping.',
            '', 'Positive values denote savings (off minus on). Percentage points use the all-off battery denominator. Pilot is excluded from confirmatory inference.', '',
            '| Policy | Estimand | Mean pp | 95% CI | Holm p | Margin |','|---|---|---:|---|---:|---|']
    for t in tests:
        ci=f'[{t["ci_low"]:.3f}, {t["ci_high"]:.3f}]' if t['ci_low'] is not None else '—'
        pv=f'{t["holm_p"]:.4g}' if t['holm_p'] is not None else '—'
        report.append(f'| {t["algorithm"]} | {t["estimand"]} | {t["mean"]:.3f} | {ci} | {pv} | {t["margin_verdict"]} |')
    report.extend(['',f'Unequal-cardinality prefix comparisons: {sum(r["prefix_unequal"] for r in seed_rows)} (excluded only from local/continuation estimands, not global effects).',
                  'Prefix sum equals whole saving by construction, not evidence of additivity. Pulse sum is a distinct, non-additive estimand. Continuation residual is an accounting contrast; it does not identify mediation by deadheading. Distance categories and service changes are descriptive.',
                  'Candidate fingerprint and pre-target trace establish observed matching history, not a formal full-state snapshot.'])
    (A/'RESULTS.md').write_text('\n'.join(report)+'\n')
    figures(A,seed_rows,round_rows,horizon_rows)
    write_json(out/'validation_report.json',{'status':'PASS','protocol_sha256':sha256_json(p),'runs':len(run_rows),'seed_count':len(p['seeds']),'analysis_sha256':sha256_file(A/'seed_effects.csv')})
    print('\n'.join(report),flush=True)


def figures(A,seeds,rounds,horizons):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    colors=['#0072B2','#D55E00']
    fig, ax=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for j,alg in enumerate(('greedy','hungarian')):
        ss=[s for s in seeds if s['algorithm']==alg]
        for i,f in enumerate(('whole_pct','pulse_sum_pct','prefix_direct_pct','prefix_continuation_pct')):
            v=np.array([s[f] for s in ss]); ax[0].scatter(np.full(len(v),i+(j-.5)*.2),v,s=12,alpha=.25,color=colors[j]); ax[0].scatter(i+(j-.5)*.2,v.mean(),marker='D',color=colors[j],label=alg if i==0 else None)
        for mode,ls in [('pulse','--'),('prefix','-')]:
            curves=[]
            for s in ss:
                rr=[r for r in rounds if r['algorithm']==alg and r['seed']==s['seed'] and r['mode']==mode]
                rr.sort(key=lambda r:r['k']); v=np.r_[0,np.cumsum([r['global_pct'] for r in rr])]
                curves.append(np.interp(np.linspace(0,1,101),np.linspace(0,1,len(v)),v))
            ax[1].plot(np.linspace(0,100,101),np.mean(curves,axis=0),ls,color=colors[j],label=f'{alg} {mode}')
    ax[0].set_xticks(range(4),['Whole','Pulse sum','Prefix local','Prefix residual'],rotation=20); ax[0].set_ylabel('Saving (% of all-off battery)'); ax[0].legend()
    ax[1].set_xlabel('Reference round progress (%)'); ax[1].set_ylabel('Cumulative effect (pp)'); ax[1].legend(fontsize=8)
    for a in ax: a.axhline(0,color='grey',lw=.7)
    for ext in ('png','pdf'): fig.savefig(A/f'impulse_prefix.{ext}',dpi=300)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4),layout='constrained')
    hs=[0,30,60,120,300,600,900,1800,'terminal']
    for j,alg in enumerate(('greedy','hungarian')):
        for mode,ls in [('pulse','--'),('prefix','-')]:
            sums={}
            for r in horizons:
                if r['algorithm']==alg and r['mode']==mode:
                    key=(r['seed'],r['horizon_s']); sums[key]=sums.get(key,0)+r['planned_saving_pct']
            y=[np.mean([v for (s,h),v in sums.items() if h==x]) for x in hs]
            ax.plot(range(len(hs)),y,ls,marker='o',color=colors[j],label=f'{alg} {mode}')
    ax.set_xticks(range(len(hs)),[str(h) for h in hs],rotation=25); ax.set_xlabel('Seconds after target (categorical spacing)')
    ax.set_ylabel('Sum of planned response effects (pp)'); ax.axhline(0,color='grey',lw=.7); ax.legend(fontsize=8)
    for ext in ('png','pdf'): fig.savefig(A/f'response_horizons.{ext}',dpi=300)
    plt.close(fig)


def identity(p,paths):
    versions={d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata['Name']}
    return {'protocol_sha256':sha256_json(p),'source_sha256':sha256_file(paths[0]),'inputs_sha256':{k:sha256_file(v) for k,v in zip(INPUT_HASHES,paths[1:])},
            'kit_sha256':sha256_json({str(f.relative_to(ROOT)):sha256_file(f) for f in sorted([ROOT/'experiment_c.py',*list((ROOT/'ugvkit').glob('*.py'))])}),
            'python_version':sys.version,'packages_sha256':sha256_json(versions),'packages':versions}


def export(out,p):
    dest=out/'exports'; dest.mkdir(exist_ok=True); zpath=dest/f'{p["protocol_id"]}_{time.strftime("%Y%m%dT%H%M%S")}.zip'
    require(not zpath.exists(),'Export already exists')
    files=[out/'validation_report.json',out/'campaign_identity.json',out/'protocol.json',out/'run_matrix.json',*sorted((out/'analysis').glob('*'))]
    with zipfile.ZipFile(zpath,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        sums=[]
        for f in files:
            name=str(f.relative_to(out)); z.write(f,name); sums.append(f'{sha256_file(f)}  {name}')
        z.writestr('SHA256SUMS.txt','\n'.join(sums)+'\n')
    with zipfile.ZipFile(zpath) as z:
        require(z.testzip() is None,'ZIP integrity failure')
        for line in z.read('SHA256SUMS.txt').decode().splitlines():
            h,n=line.split('  ',1); require(hashlib.sha256(z.read(n)).hexdigest()==h,'Export hash mismatch')
    print(f'EXPORT VERIFIED: {zpath}',flush=True)
    return zpath


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('action',choices=['run','status','validate']); ap.add_argument('--pilot',action='store_true')
    ap.add_argument('--repo',required=True); ap.add_argument('--out-root',required=True); ap.add_argument('--jobs',type=int,default=2); ap.add_argument('--timeout',type=int,default=3600)
    a=ap.parse_args(); p=protocol(a.pilot); base=Path(a.out_root).expanduser().resolve(); out=base/('pilot_C' if a.pilot else 'experiment_C_impulse')
    require(a.jobs>=1,'jobs must be positive')
    if a.action=='status':
        expected=len(load_json(out/'run_matrix.json')) if (out/'run_matrix.json').exists() else None
        count=sum(1 for f in (out/'runs').glob('*/RUN_OK.json')); failed=sum(1 for f in (out/'runs').glob('*/RUN_FAILED.json'))
        print(f'{out}: {count} completion markers, {failed} failure markers, expected {expected if expected is not None else "determined after references"}'); return
    paths=repo_paths(a.repo); ident=identity(p,paths)
    require(ident['source_sha256']==FROZEN_APP_SHA256 and ident['inputs_sha256']==INPUT_HASHES,'Frozen simulator or input SHA-256 mismatch')
    if not a.pilot:
        po=base/'pilot_C'; gate=load_json(po/'validation_report.json'); pilotident=load_json(po/'campaign_identity.json')
        proof=load_json(po/'PILOT_OK.json')
        require(gate['status']=='PASS' and gate['protocol_sha256']==sha256_json(protocol(True)) and pilotident==identity(protocol(True),paths) and gate['analysis_sha256']==sha256_file(po/'analysis'/'seed_effects.csv') and proof['validation_sha256']==sha256_file(po/'validation_report.json') and proof['zip_sha256']==sha256_file(po/'exports'/proof['zip']),'Pilot gate not satisfied by this exact kit/input/protocol')
    out.mkdir(parents=True,exist_ok=True)
    with open(out/'.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        marker=out/'campaign_identity.json'
        if marker.exists(): require(load_json(marker)==ident,'Campaign identity differs; use new output root')
        else:
            require(not any(f.name!='.lock' for f in out.iterdir()),'Nonempty foreign campaign folder')
            write_json(marker,ident); write_json(out/'protocol.json',p)
        require(load_json(out/'protocol.json')==p,'Frozen protocol mismatch')
        write_json(out/'validation_report.json',{'status':'IN_PROGRESS','protocol_sha256':sha256_json(p)})
        ref=references(p)
        if a.action=='run': batch(out,ref,paths,a.jobs,a.timeout)
        if a.pilot:
            for seed in p['seeds']:
                for alg in p['algorithms']:
                    for mode in ('off','on'):
                        end_equal(inspect(out,spec(p,seed,alg,mode)),inspect(out,spec(p,seed,alg,'control_'+mode)))
        extended=expand(out,p); matrix=ref+extended
        if (out/'run_matrix.json').exists(): require(load_json(out/'run_matrix.json')==matrix,'Expanded run matrix changed')
        else: write_json(out/'run_matrix.json',matrix)
        print(f'Exact campaign count: {len(matrix)}; estimated disk {len(matrix)*2.5/1024:.1f} GiB at 2.5 MB/run',flush=True)
        if a.action=='run':
            remaining=sum(not (out/'runs'/s['label']/'RUN_OK.json').exists() for s in extended)
            need=remaining*3*1024**2+512*1024**2
            if remaining:
                require(shutil.disk_usage(out).free>=need,f'Insufficient estimated free disk: need {need/1024**3:.1f} GiB for remaining runs (3 MiB/run + 512 MiB reserve). Free space or use a new output root on a larger disk before continuing.')
        if a.pilot and a.action=='run':
            # Check both first-round interventions and the all-on endpoint before the whole ladder.
            early=[]
            for seed in p['seeds']:
                for alg in p['algorithms']:
                    on=inspect(out,spec(p,seed,alg,'on')); end=len(on['trace'])
                    early.extend([spec(p,seed,alg,'pulse',1),spec(p,seed,alg,'prefix',1),spec(p,seed,alg,'prefix',end)])
            batch(out,list({s['label']:s for s in early}.values()),paths,a.jobs,a.timeout)
            for seed in p['seeds']:
                for alg in p['algorithms']:
                    off=inspect(out,spec(p,seed,alg,'off')); on=inspect(out,spec(p,seed,alg,'on'))
                    for mode in ('pulse','prefix'): target_check(off,inspect(out,spec(p,seed,alg,mode,1)),1)
                    end=inspect(out,spec(p,seed,alg,'prefix',len(on['trace'])))
                    end_equal(end,on); require(end['trace']==on['trace'],'Pilot all-on endpoint mismatch')
        if a.action=='run': batch(out,extended,paths,a.jobs,a.timeout)
        analyze(out,p,extended); zpath=export(out,p)
        if a.pilot: write_json(out/'PILOT_OK.json',{'validation_sha256':sha256_file(out/'validation_report.json'),'zip':zpath.name,'zip_sha256':sha256_file(zpath)})


if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try: main()
    except KeyboardInterrupt:
        halt(); print('Interrupted; rerun identical command to resume.',file=sys.stderr); sys.exit(130)
    except Exception as e:
        print(f'STOP: {e}',file=sys.stderr); sys.exit(1)
