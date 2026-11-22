"""Resumable, paired, external-measurement-anchored sensitivity experiment."""
import argparse, csv, fcntl, hashlib, importlib.metadata, itertools, json, math, os, shutil, signal, subprocess, sys, threading, time, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from calibrate_F import CAL, ROOT, calculate
from ugvkit.common import BASE_CLI, BASE_ENV, load_json, write_json, sha256_file, sha256_json, repo_paths, seeds_from, spec_hash
from ugvkit.launch import check_run
from ugvkit import FROZEN_APP_SHA256

STOP=threading.Event(); LOCK=threading.Lock(); ACTIVE=set()
FILES=('run_summary.csv','run_settings.json','backend_source.py','canonical_requests.csv','canonical_requests.sha256','vehicle_soc_snapshots.csv','energy_feasibility_summary.csv','cost_diagnostics.csv','request_results.csv','request_wait_diagnostics.csv','vehicle_results.csv','assignment_events.csv')
METRICS=('battery_Wh','completed','wait_s','ride_s','Wh_per_completed','km','grid_Wh','energy_blocked_insertions')
def rows(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def require(x,msg):
    if not x: raise ValueError(msg)
def csvout(path,rs):
    require(rs,'Empty output');
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def protocol():return load_json(ROOT/'protocols/experiment_F.json')
def matrix(p,pilot,inputs):
    seeds=p['pilot_seeds'] if pilot else seeds_from(p['seeds']); result=[]
    for seed,(cfg,soc,alg,alpha) in itertools.product(seeds,itertools.product(p['configs'],p['initial_soc'],p['algorithms'],p['alpha_energy'])):
        result.append(dict(label=f'F__{cfg}__soc{int(soc*100)}__{alg}__a{alpha}__seed{seed}',protocol_id=p['protocol_id'],seed=seed,network='UTP',config=cfg,window_s=1800,algorithm=alg,alpha_energy=alpha,vehicles=12,requests=100,initial_soc=soc,beta_time=1.,soc_cost_weight=0.,source_sha256=FROZEN_APP_SHA256,input_hashes=inputs['UTP'],registry_sha256=None,overrides={'UGV_C_RR':p['configs'][cfg]},probe={'enabled':False},cli=dict(BASE_CLI),env=dict(BASE_ENV)))
    require(len(result)==p['pilot_runs' if pilot else 'confirmatory_runs'] and len({s['label'] for s in result})==len(result),'Unexpected matrix size')
    return result

def hashes(rd,res,sp):
    paths=[rd/'run_spec.json',rd/'app.py',rd/'utp_graph.graphml',rd/'hotspot_locations.csv',rd/'overrides_and_provenance.json',*[res/n for n in FILES]]
    if sp['network']=='UM_district':paths.append(rd/'parking_registry.json')
    return {str(f.relative_to(rd)):sha256_file(f) for f in paths}

def inspect(out,sp,aud):
    rd=out/'runs'/sp['label']; ok=load_json(rd/'RUN_OK.json'); res=(rd/ok['results_dir']).resolve()
    require(res.parent==(rd/'results').resolve() and ok['spec_hash']==spec_hash(sp) and load_json(rd/'run_spec.json')==sp,'Spec/result location mismatch')
    require(ok['files']==hashes(rd,res,sp),'Invalid or corrupted output hash')
    require(sha256_file(rd/'app.py')==sha256_file(res/'backend_source.py')==FROZEN_APP_SHA256,'Source mismatch')
    require({k:sha256_file(rd/k) for k in sp['input_hashes']}==sp['input_hashes'],'Input mismatch')
    prov=load_json(rd/'overrides_and_provenance.json'); settings=load_json(res/'run_settings.json'); params=settings['parameters']
    require(prov['network']==sp['network'] and prov['inputs_sha256']==sp['input_hashes'] and prov['app_sha256']==FROZEN_APP_SHA256 and prov['exit_code']==0,'Provenance mismatch')
    if sp['network']=='UM_district':require(prov['registry_sha256']==sha256_file(rd/'parking_registry.json')==sp['registry_sha256'],'Registry mismatch')
    require(settings['input_files']['road_graph']['sha256']==sp['input_hashes']['utp_graph.graphml'] and settings['input_files']['hotspots']['sha256']==sp['input_hashes']['hotspot_locations.csv'],'Simulator input mismatch')
    require(all(float(params[k])==v for k,v in {'ARRIVAL_WINDOW_S':1800,'UGV_EMPTY_MASS_KG':825,'UGV_PASSENGER_MASS_KG':80,'UGV_C_RR':sp['overrides']['UGV_C_RR'],'UGV_ETA':.9,'UGV_DRIVING_AUX_POWER_W':50,'UGV_IDLE_POWER_W':50,'DWELL_AUX_POWER_W':50,'BATTERY_CAPACITY_WH':9000,'BATTERY_RESERVE_FRACTION':.2}.items()),'Parameter mismatch')
    ss=rows(res/'run_summary.csv'); require(len(ss)==1,'Summary count');s=ss[0]
    for k,v in {'trial_seed':sp['seed'],'fleet_size':12,'spawned_requests':100,'initial_soc_low':sp['initial_soc'],'initial_soc_high':sp['initial_soc'],'alpha_energy':sp['alpha_energy'],'beta_time':1,'soc_cost_weight':0,'energy_reference_Wh':100,'time_reference_s':600,'dispatch_window_s':30,'dispatch_urgent_slack_s':60}.items():require(float(s[k])==v,f'Wrong {k}')
    require(s['algorithm']==sp['algorithm'] and s['scenario']=='S4' and s['cost_mode']=='normalized' and s['depot_ids']=='P02;P08;P16','Wrong policy/depot settings')
    dp=aud['depots'][sp['network']];snap=rows(res/'vehicle_soc_snapshots.csv'); tick=snap[0]['tick']; fleet=sorted((r['vehicle_id'],r['home_depot_id'],float(r['initial_SOC_Wh'])) for r in snap if r['tick']==tick)
    require(len(fleet)==12 and len(set(r[0] for r in fleet))==12 and all(r[2]==9000*sp['initial_soc'] for r in fleet) and all(sum(r[1]==k for r in fleet)==4 for k in dp),'Initial fleet mismatch')
    require(all(int(r['home_depot_node'])==dp[r['home_depot_id']] for r in snap),'Mapped depot node mismatch')
    canonical=rows(res/'canonical_requests.csv'); canonical_hash=sha256_file(res/'canonical_requests.csv')
    require(canonical_hash==(res/'canonical_requests.sha256').read_text().split()[0]==ok['canonical_requests_sha256'],'Canonical hash mismatch')
    mapnode=lambda n:aud['um_to_utp'][int(n)] if sp['network']=='UM_district' else int(n)
    od=[(int(r['request_id']),mapnode(r['pickup_node']),mapnode(r['dropoff_node']),int(r['max_wait_s'])) for r in canonical]; arrivals=[float(r['arrival_time_s']) for r in canonical]
    require(len(od)==100 and [r[0] for r in od]==list(range(1,101)) and len({r[1:3] for r in od})==100 and all(r[1]!=r[2] for r in od),'Invalid canonical OD')
    require(arrivals==sorted(arrivals) and all(0<=t<=sp['window_s'] for t in arrivals),'Arrival-window mismatch')
    req=rows(res/'request_results.csv');done=int(s['completed_requests']); require(len(req)==100 and done+int(s['uncompleted_requests'])==100 and sum(int(r['request_completed']) for r in req)==done,'Completion accounting mismatch')
    ev=rows(res/'assignment_events.csv'); energy=math.fsum(float(r['predicted_incremental_route_energy_Wh']) for r in ev); bat=float(s['total_battery_withdrawn_Wh'])
    require(math.isfinite(bat) and bat>0 and abs(energy-bat)<=.005*bat,'Assignment energy/battery mismatch')
    d=rows(res/'cost_diagnostics.csv'); require(len(d)==int(s['matching_round_count']) and len(ev)==int(s['matching_selected_pairs_total']),'Dispatch/assignment count mismatch')
    ce,ct,cross=[math.fsum(float(r[k]) for r in d if r[k]) for k in ('within_request_energy_ss','within_request_time_ss','within_request_cross_sum')]
    def num(k): return float(s[k]) if s[k] else None
    blocked=int(rows(res/'energy_feasibility_summary.csv')[0]['energy_blocked_insertions']);require(blocked>=0,'Invalid blocking count')
    metrics=dict(battery_Wh=bat,completed=done,wait_s=num('mean_deadline_limited_pickup_wait_s'),ride_s=num('mean_passenger_time_s'),Wh_per_completed=bat/done if done else None,km=num('total_distance_km'),grid_Wh=num('total_grid_import_Wh'),corr_energy_ss=ce,corr_time_ss=ct,corr_cross=cross,energy_time_r=cross/math.sqrt(ce*ct) if ce*ct>0 else None,assignment_energy_Wh=energy,energy_blocked_insertions=blocked)
    require(all(math.isfinite(v) for v in metrics.values() if v is not None),'Nonfinite metric')
    return dict(spec=sp,metrics=metrics,workload=canonical_hash,od=od,arrivals=arrivals,fleet=fleet)

def run_one(out,sp,aud,paths,timeout):
    if STOP.is_set():return 'stopped'
    rd=out/'runs'/sp['label']; ok=rd/'RUN_OK.json'
    if ok.exists():
        try:inspect(out,sp,aud);return 'skipped'
        except Exception as e:
            require(load_json(rd/'run_spec.json')==sp,'Existing completed run has different spec; refusing to touch')
            print(f'Quarantining invalid run {rd.name}: {e}',flush=True)
    if rd.exists():
        dest=out/'_incomplete'/f'{rd.name}__{time.time_ns()}';dest.parent.mkdir(exist_ok=True);shutil.move(rd,dest)
    rd.mkdir(parents=True)
    src=paths[sp['network']]
    for f,n in zip(src,('app.py','utp_graph.graphml','hotspot_locations.csv','parking_registry.json')):shutil.copy2(f,rd/n)
    write_json(rd/'run_spec.json',sp)
    try:
        with (rd/'stdout.txt').open('w') as so,(rd/'stderr.txt').open('w') as se:
            with LOCK:
                if STOP.is_set():return 'stopped'
                proc=subprocess.Popen([sys.executable,str(ROOT/'ugvkit/runner.py'),'--run-dir',str(rd)],cwd=rd,env=dict(os.environ,**sp['env']),stdout=so,stderr=se,start_new_session=True);ACTIVE.add(proc)
            try:proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();raise
            finally:
                with LOCK:ACTIVE.discard(proc)
        require(proc.returncode==0,f'Simulator exit {proc.returncode}; see {rd}/stderr.txt')
        success,info=check_run(rd,sp);require(success,str(info));res=rd/info['results_dir']
        write_json(ok,dict(info,spec_hash=spec_hash(sp),files=hashes(rd,res,sp)))
        try:inspect(out,sp,aud)
        except Exception:ok.unlink();raise
        return 'ok'
    except Exception as e:write_json(rd/'RUN_FAILED.json',{'error':str(e)});return f'FAILED: {e}'

def halt():
    STOP.set()
    with LOCK:
        for proc in ACTIVE:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass

def batch(out,specs,aud,paths,jobs,timeout):
    bad=[]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        fs={pool.submit(run_one,out,s,aud,paths,timeout):s for s in specs}
        try:
            for n,f in enumerate(as_completed(fs),1):
                stat=f.result(); label=fs[f]['label']
                if stat not in ('ok','skipped'):bad.append((label,stat))
                if stat!='skipped' or n%50==0:print(f'[{n}/{len(specs)}] {stat} {label}',flush=True)
                if bad:halt();pool.shutdown(wait=True,cancel_futures=True);break
        except BaseException:halt();pool.shutdown(wait=True,cancel_futures=True);raise
    require(not bad,f'Campaign stopped at first failure: {bad[:1]}; inspect stderr then resume')

def verify_pairs(data,p,seeds):
    for seed in seeds:
        ds=[data[seed,n,w,a,e] for n,w,a,e in itertools.product(p['configs'],p['initial_soc'],p['algorithms'],p['alpha_energy'])];ref=ds[0]
        require(all(d['workload']==ref['workload'] and d['od']==ref['od'] and d['arrivals']==ref['arrivals'] and [r[:2] for r in d['fleet']]==[r[:2] for r in ref['fleet']] for d in ds),'Workload or fleet pairing mismatch')
        for w in p['initial_soc']:
            group=[data[seed,n,w,a,e] for n,a,e in itertools.product(p['configs'],p['algorithms'],p['alpha_energy'])]
            require(all(d['fleet']==group[0]['fleet'] for d in group),'Within-SOC initial fleet mismatch')

def analyze(out,p,pilot,specs,aud):
    import numpy as np
    from scipy import stats
    a=out/'analysis';a.mkdir(exist_ok=True);data={};flat=[];paired=[];means=[];primary=[];secondary=[]
    seeds=p['pilot_seeds'] if pilot else seeds_from(p['seeds']); cells=list(itertools.product(p['configs'],p['initial_soc'],p['algorithms']))
    for sp in specs:
        d=inspect(out,sp,aud); key=(sp['seed'],sp['config'],sp['initial_soc'],sp['algorithm'],sp['alpha_energy']);data[key]=d
        flat.append(dict(label=sp['label'],seed=key[0],config=key[1],Crr=p['configs'][key[1]],initial_soc=key[2],algorithm=key[3],alpha=key[4],workload=d['workload'],**d['metrics']))
    verify_pairs(data,p,seeds); csvout(a/'run_level.csv',flat)
    rng=np.random.default_rng(p['inference']['randomization_seed']); draws=p['inference']['randomization_draws']
    def ci(vals):
        x=np.array([v for v in vals if v is not None],float);n=len(x)
        if not n:return dict(n=0,mean=None,ci_low=None,ci_high=None)
        m=float(x.mean());h=float(stats.t.ppf(.975,n-1)*x.std(ddof=1)/math.sqrt(n)) if n>1 else None
        return dict(n=n,mean=m,ci_low=m-h if h is not None else None,ci_high=m+h if h is not None else None)
    def contrast(family,name,vals):
        r=dict(family=family,contrast=name,**ci(vals)); x=np.array(vals);count=0
        for start in range(0,draws,5000):
            signs=rng.integers(0,2,(min(5000,draws-start),len(x)))*2-1;count+=int(np.sum(np.abs((signs*x).mean(axis=1))>=abs(r['mean'])-1e-12))
        r.update(p=(count+1)/(draws+1),holm_p=None);primary.append(r)
    def avg(rs,k):
        x=[r[k] for r in rs if r[k] is not None];return float(np.mean(x)) if x else None
    effects={}; service={}
    for n,w,alg in cells:
        label=f'{n} / SOC {int(w*100)}% / {alg}'
        for alpha in p['alpha_energy']:
            rs=[data[s,n,w,alg,alpha]['metrics'] for s in seeds]; ce=sum(r['corr_energy_ss'] for r in rs);ct=sum(r['corr_time_ss'] for r in rs)
            means.append(dict(config=n,initial_soc=w,algorithm=alg,alpha=alpha,n=len(rs),**{k:avg(rs,k) for k in METRICS},energy_time_r=sum(r['corr_cross'] for r in rs)/math.sqrt(ce*ct) if ce*ct>0 else None))
        prs=[]
        for s in seeds:
            x,y=[data[s,n,w,alg,e]['metrics'] for e in [0,1]]
            z=dict(seed=s,config=n,initial_soc=w,algorithm=alg,battery_saving_pct=100*(x['battery_Wh']-y['battery_Wh'])/x['battery_Wh'])
            for k in METRICS:z[k+'_on_minus_off']=y[k]-x[k] if y[k] is not None and x[k] is not None else None
            prs.append(z);paired.append(z)
        effects[n,w,alg]=[r['battery_saving_pct'] for r in prs];service[label]=ci([r['completed_on_minus_off'] for r in prs])
        for k in METRICS:secondary.append(dict(cell=label,metric=k+'_on_minus_off',**ci([r[k+'_on_minus_off'] for r in prs])))
        if not pilot:contrast('simple',label,effects[n,w,alg])
    csvout(a/'condition_means.csv',means);csvout(a/'paired_seed_effects.csv',paired);csvout(a/'secondary_intervals.csv',secondary)
    if not pilot:
        for n,w,alg in itertools.product(('LOW','HIGH'),p['initial_soc'],p['algorithms']):contrast('interaction',f'{n} minus BASE / SOC {int(w*100)}% / {alg}',[y-x for x,y in zip(effects['BASE',w,alg],effects[n,w,alg])])
        for n,alg in itertools.product(p['configs'],p['algorithms']):contrast('interaction',f'25% minus 100% / {n} / {alg}',[y-x for x,y in zip(effects[n,1.,alg],effects[n,.25,alg])])
        for family,count in p['inference']['holm_families'].items():
            group=sorted([r for r in primary if r['family']==family],key=lambda r:r['p']);require(len(group)==count,'Contrast family mismatch');prev=0.
            for i,r in enumerate(group):prev=max(prev,min(1.,r['p']*(count-i)));r['holm_p']=prev
        for r in primary:
            q=service.get(r['contrast']);r['completion_diff']=q['mean'] if q else None;r['completion_ci_low']=q['ci_low'] if q else None;r['completion_ci_high']=q['ci_high'] if q else None
            r['service_guard_met']=bool(q and q['ci_low']>-1) if q else None
            r['energy_benefit_supported']=bool(r['mean']>0 and r['holm_p']<.05 and r['service_guard_met']) if q else None
        csvout(a/'primary_contrasts.csv',primary)
        figures(a,primary)
    report=['# Experiment F — validation and results','',f'{len(flat)} validated runs, {len(seeds)} paired seeds.','PASS: frozen source, fixed UTP inputs, depot nodes, settings, canonical hashes, workload, fleet, completion and battery accounting.','Pilot excluded from inference. Positive savings denote lower withdrawal; interactions are percentage-point differences.','']
    if pilot:report+=['PILOT PASS — all 24 cells verified; no confirmatory inference.']
    else:
        report+=['| Contrast | Mean pp | 95% CI | Holm p | Service guard |','|---|---:|---:|---:|---|']
        for r in primary:report.append(f"| {r['contrast']} | {r['mean']:.3f} | [{r['ci_low']:.3f}, {r['ci_high']:.3f}] | {r['holm_p']:.4g} | {'met' if r['service_guard_met'] else 'not met' if r['service_guard_met'] is not None else '—'} |")
        report+=['','The completion guard is descriptive, not a multiplicity-adjusted noninferiority test. No energy-benefit claim for a cell failing the guard.']
    report+=['',p['limitations']];(a/'results.md').write_text('\n'.join(report)+'\n');print('\n'.join(report),flush=True)
    write_json(out/'validation_report.json',dict(status='PASS',protocol_sha256=sha256_json(p),pilot=pilot,expected=len(specs),validated=len(flat),analysis_sha256=sha256_file(a/'run_level.csv')))

def figures(a,primary):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for family in ('simple','interaction'):
        rs=[r for r in primary if r['family']==family];fig,ax=plt.subplots(figsize=(9,6.8),layout='constrained')
        for i,r in enumerate(rs):ax.errorbar(r['mean'],i,xerr=[[r['mean']-r['ci_low']],[r['ci_high']-r['mean']]],fmt='o',color='#0072B2',capsize=3)
        ax.axvline(0,color='gray',lw=.8);ax.set_yticks(range(len(rs)),[r['contrast'] for r in rs]);ax.invert_yaxis();ax.set_xlabel('Battery saving (%)' if family=='simple' else 'Difference in saving (pp)')
        for ext in ('png','pdf'):fig.savefig(a/f'{family}_forest.{ext}',dpi=300)
        plt.close(fig)

def export(out,p,pilot):
    dest=out/'exports';dest.mkdir(exist_ok=True);zpath=dest/f"{p['protocol_id']}{'_PILOT' if pilot else ''}_{time.strftime('%Y%m%dT%H%M%S')}_{time.time_ns()%1000000:06d}.zip"
    files=[out/'validation_report.json',out/'campaign_identity.json',out/'protocol.json',out/'run_matrix.json',*sorted((out/'analysis').glob('*')),*sorted(CAL.glob('*')),ROOT/'calibrate_F.py']
    with zipfile.ZipFile(zpath,'x',compression=zipfile.ZIP_DEFLATED) as z:
        sums=[]
        for f in files:
            name=str(f.relative_to(out)) if f.is_relative_to(out) else 'calibration/'+f.name;z.write(f,name);sums.append(f'{sha256_file(f)}  {name}')
        z.writestr('SHA256SUMS.txt','\n'.join(sums)+'\n')
    with zipfile.ZipFile(zpath) as z:
        require(z.testzip() is None,'Export corruption')
        for line in z.read('SHA256SUMS.txt').decode().splitlines():
            h,n=line.split('  ',1);require(hashlib.sha256(z.read(n)).hexdigest()==h,'Export hash mismatch')
    print('EXPORT VERIFIED:',zpath,flush=True);return zpath

def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['run','status','validate']);ap.add_argument('--pilot',action='store_true');ap.add_argument('--repo',default='~/ugv-benchmark-public');ap.add_argument('--out-root',default='~/ugv_v7_campaigns');ap.add_argument('--jobs',type=int,default=2);ap.add_argument('--timeout',type=int,default=7200);args=ap.parse_args()
    p=protocol();base=Path(args.out_root).expanduser().resolve();out=base/('pilot_F' if args.pilot else 'experiment_F_sensitivity')
    if args.action=='status':
        n=p['pilot_runs' if args.pilot else 'confirmatory_runs'];done=len(list((out/'runs').glob('*/RUN_OK.json')));bad=len(list((out/'runs').glob('*/RUN_FAILED.json')));print(f'{done}/{n} completion markers; {n-done} remaining; {bad} failures');return
    require(args.jobs>0,'Jobs must be positive');src=repo_paths(args.repo);require([sha256_file(f) for f in src]==[FROZEN_APP_SHA256,'ebd138a83763f11172e079f40457b371be7eebcd2e3aa018aeda13d9d70114f4','6a55a275f2ac18ab383d2efcd67a31250602503a62fa3c5bf2f3f504ae0b979d'],'Source/input mismatch');aud={'depots':{'UTP':{'P02':6182889058,'P08':6182889469,'P16':6273985132}}};paths={'UTP':src};inputs={'UTP':{'utp_graph.graphml':sha256_file(src[1]),'hotspot_locations.csv':sha256_file(src[2])}}
    summary,*_=calculate();require(summary['configs']==p['configs'] and summary['source_sha256']==p['measurement_sha256'],'Calibration anchors mismatch')
    specs=matrix(p,args.pilot,inputs);versions={d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata['Name']}
    ident=dict(protocol_sha256=sha256_json(p),source_sha256=FROZEN_APP_SHA256,inputs=inputs,calibration_sha256={f.name:sha256_file(f) for f in sorted(CAL.glob('*'))},kit_sha256=sha256_json({str(f.relative_to(ROOT)):sha256_file(f) for f in sorted([*ROOT.glob('*.py'),*ROOT.glob('*.sh'),*(ROOT/'ugvkit').glob('*.py')])}),python=sys.version,packages=versions)
    if not args.pilot:
        po=base/'pilot_F';gate=load_json(po/'validation_report.json');proof=load_json(po/'PILOT_OK.json')
        require(load_json(po/'campaign_identity.json')==ident and gate['status']=='PASS' and gate['pilot'] and gate['validated']==24 and gate['analysis_sha256']==sha256_file(po/'analysis/run_level.csv') and proof['validation_sha256']==sha256_file(po/'validation_report.json') and proof['zip_sha256']==sha256_file(po/'exports'/proof['zip']),'Pilot gate failed')
    out.mkdir(parents=True,exist_ok=True)
    with (out/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);marker=out/'campaign_identity.json'
        if marker.exists():require(load_json(marker)==ident,'Campaign identity changed; refusing to mix runs')
        else:
            require(not any(f.name!='.lock' for f in out.iterdir()),'Nonempty foreign campaign folder');write_json(marker,ident);write_json(out/'protocol.json',p);write_json(out/'run_matrix.json',specs)
        require(load_json(out/'protocol.json')==p and load_json(out/'run_matrix.json')==specs,'Protocol/matrix mismatch')
        if args.action=='run':
            remaining=sum(not (out/'runs'/s['label']/'RUN_OK.json').exists() for s in specs);need=remaining*4*1024**2+512*1024**2;require(shutil.disk_usage(out).free>=need,f'Need estimated {need/1024**3:.2f} GiB free')
        write_json(out/'validation_report.json',dict(status='IN_PROGRESS',protocol_sha256=sha256_json(p)))
        if args.action=='run':batch(out,specs,aud,paths,args.jobs,args.timeout)
        analyze(out,p,args.pilot,specs,aud);z=export(out,p,args.pilot)
        if args.pilot:write_json(out/'PILOT_OK.json',dict(validation_sha256=sha256_file(out/'validation_report.json'),zip=z.name,zip_sha256=sha256_file(z)))

if __name__=='__main__':
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:main()
    except KeyboardInterrupt:halt();print('Interrupted; rerun same command.',file=sys.stderr);sys.exit(130)
    except Exception as e:print('STOP:',e,file=sys.stderr);sys.exit(1)
