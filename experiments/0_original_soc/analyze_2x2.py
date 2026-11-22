"""Paired analysis of the S4 energy-weight (alpha_E 0/1) x initial-SOC (100%/25%) experiment.
usage: python analyze_2x2.py OUT_ROOT [--mc 1000000] [--margin-pp 1.0] [--margin-wh 100]
Unit of analysis = workload seed. Everything is paired within seed.
Effect at a SOC level  D_soc = Y(alpha=1) - Y(alpha=0)
Interaction            I     = D_25 - D_100     (does the energy term matter differently when energy is scarce?)
Primary family (Holm, 4 tests): I on completions and on battery Wh, for Hungarian and Greedy.
"""
import csv, glob, os, sys, math, argparse, collections
import numpy as np
from scipy import stats
ap=argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--mc',type=int,default=1_000_000)
ap.add_argument('--margin-pp',type=float,default=1.0); ap.add_argument('--margin-wh',type=float,default=100.0)
ap.add_argument('--boot',type=int,default=20000); a=ap.parse_args()
rows={}
for f in glob.glob(os.path.join(a.out,'*','results','*','run_summary.csv')):
    r=next(csv.DictReader(open(f)))
    k=(r['algorithm'],float(r['initial_soc_low']),int(float(r['alpha_energy'])),int(r['trial_seed']))
    if k in rows: raise SystemExit(f'duplicate run {k}')
    rows[k]=dict(done=int(r['completed_requests']),bat=float(r['total_battery_withdrawn_Wh']),km=float(r['total_distance_km']),
                 wait=float(r['mean_deadline_limited_pickup_wait_s']),grid=float(r['total_grid_import_Wh']))
algs=sorted({k[0] for k in rows}); seeds=sorted({k[3] for k in rows})
for al in algs:
  for soc in (1.0,0.25):
    for x in (0,1):
      miss=[s for s in seeds if (al,soc,x,s) not in rows]
      if miss: raise SystemExit(f'missing {al} soc={soc} alpha={x} seeds {miss}')
n=len(seeds); rng=np.random.default_rng(20261119)
def signflip(d):
    d=np.asarray(d,float); obs=abs(d.sum())
    if np.allclose(d,np.round(d)):              # exact via dynamic programming over integer sums
        dist={0:1}
        for v in d.astype(int):
            nd=collections.defaultdict(int)
            for s,c in dist.items(): nd[s+v]+=c; nd[s-v]+=c
            dist=nd
        return sum(c for s,c in dist.items() if abs(s)>=obs-1e-9)/2**n, 'exact'
    if n<=22:
        signs=((np.arange(2**n)[:,None]>>np.arange(n))&1)*2-1
        return float(np.mean(np.abs(signs@d)>=obs-1e-9)),'exact'
    hits=0; done=0
    while done<a.mc:
        m=min(200_000,a.mc-done); e=rng.choice([-1.0,1.0],size=(m,n)); hits+=int(np.sum(np.abs(e@d)>=obs-1e-9)); done+=m
    return (hits+1)/(a.mc+1),'monte-carlo'
def tci(d):
    d=np.asarray(d,float); m=d.mean(); se=d.std(ddof=1)/math.sqrt(n); h=stats.t.ppf(.975,n-1)*se; return m,m-h,m+h,d.std(ddof=1)
def holm(ps):
    o=np.argsort(ps); adj=np.empty(len(ps)); run=0
    for i,j in enumerate(o): run=max(run,min(1,(len(ps)-i)*ps[j])); adj[j]=run
    return adj
def Y(al,soc,x,var): return np.array([rows[(al,soc,x,s)][var] for s in seeds])
perseed=open(os.path.join(a.out,'..','paired_differences_by_seed.csv') if False else 'paired_differences_by_seed.csv','w',newline='')
w=csv.writer(perseed); w.writerow(['algorithm','seed','D100_completed','D25_completed','I_completed','D100_battery_Wh','D25_battery_Wh','I_battery_Wh'])
fam=[]; lines=[]
for al in algs:
    D={ (soc,v): Y(al,soc,1,v)-Y(al,soc,0,v) for soc in (1.0,0.25) for v in ('done','bat','km','wait')}
    for i,s in enumerate(seeds): w.writerow([al,s,D[(1.0,'done')][i],D[(0.25,'done')][i],D[(0.25,'done')][i]-D[(1.0,'done')][i],
                                             round(D[(1.0,'bat')][i],3),round(D[(0.25,'bat')][i],3),round(D[(0.25,'bat')][i]-D[(1.0,'bat')][i],3)])
    for v,unit,marg in (('done','completions/100 (=pp)',a.margin_pp),('bat','Wh/run',a.margin_wh)):
        I=D[(0.25,v)]-D[(1.0,v)]; m,lo,hi,sd=tci(I); p,kind=signflip(I)
        fam.append(dict(al=al,v=v,unit=unit,m=m,lo=lo,hi=hi,sd=sd,p=p,kind=kind,marg=marg))
    for soc in (1.0,0.25):
        for v,unit in (('done','pp'),('bat','Wh'),('km','km'),('wait','s')):
            m,lo,hi,sd=tci(D[(soc,v)]); p,kind=signflip(D[(soc,v)])
            lines.append(f"| {al} | {int(soc*100)}% | {v} | {m:+.2f} {unit} | [{lo:+.2f}, {hi:+.2f}] | {sd:.2f} | {p:.4g} ({kind}) |")
adj=holm(np.array([f['p'] for f in fam]))
print(f'# Energy-weight x initial-SOC experiment: {n} matched seeds, policies {algs}\n')
print('## Primary family: interaction I = (alpha1-alpha0 at 25% SOC) - (alpha1-alpha0 at 100% SOC), Holm over 4\n')
print('| Policy | Outcome | Mean I | 95% t CI | SD | sign-flip p | Holm p | CI inside +/- margin? |'); print('|---|---|---|---|---|---|---|---|')
for f,h in zip(fam,adj):
    eq='yes' if (-f['marg']<f['lo'] and f['hi']<f['marg']) else 'no'
    print(f"| {f['al']} | {f['unit']} | {f['m']:+.2f} | [{f['lo']:+.2f}, {f['hi']:+.2f}] | {f['sd']:.2f} | {f['p']:.4g} ({f['kind']}) | {h:.4g} | {eq} (+/-{f['marg']:g}) |")
print('\n## Simple effects of the energy term at each SOC level (alpha1 - alpha0; unadjusted, descriptive)\n')
print('| Policy | SOC | Outcome | Mean | 95% t CI | SD | sign-flip p |'); print('|---|---|---|---|---|---|---|'); print('\n'.join(lines))
print('\n## Energy, service and energy per completed request reported together (sums over seeds)\n')
print('| Policy | SOC | alpha | Completed | Fulfil % | Battery Wh/run | Wh per completion | 95% paired-bootstrap CI of ratio change (a1 vs a0) |'); print('|---|---|---|---|---|---|---|---|')
for al in algs:
  for soc in (1.0,0.25):
    b={x:Y(al,soc,x,'bat') for x in (0,1)}; c={x:Y(al,soc,x,'done') for x in (0,1)}
    idx=rng.integers(0,n,size=(a.boot,n))
    ratio=lambda x,ii: b[x][ii].sum(-1)/c[x][ii].sum(-1)
    dr=ratio(1,idx)-ratio(0,idx); lo,hi=np.percentile(dr,[2.5,97.5])
    for x in (0,1):
        ci=f'[{lo:+.2f}, {hi:+.2f}] Wh' if x==1 else ''
        print(f'| {al} | {int(soc*100)}% | {x} | {int(c[x].sum())}/{100*n} | {c[x].sum()/n:.2f} | {b[x].mean():.1f} | {b[x].sum()/c[x].sum():.2f} | {ci} |')
print('\nPer-seed differences written to paired_differences_by_seed.csv')
