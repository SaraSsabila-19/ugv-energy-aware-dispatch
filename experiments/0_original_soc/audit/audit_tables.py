import csv, sys, itertools, math, statistics as st, collections
R=sys.argv[1]
def rd(p): return list(csv.DictReader(open(f"{R}/{p}")))
P=rd('data/primary/run_level_640.csv'); S5=rd('data/s5/run_level_160.csv'); A=rd('data/ablation/holdout_paired.csv')
def signflip_exact(d, tol=1e-9):
    # exact two-sided via enumeration of achievable sums (works for ints/floats with n<=20 via DP on floats -> use dict)
    n=len(d); obs=abs(sum(d)); dist={0.0:1}
    for x in d:
        nd=collections.defaultdict(int)
        for s,c in dist.items():
            nd[round(s+x,6)]+=c; nd[round(s-x,6)]+=c
        dist=nd
    return sum(c for s,c in dist.items() if abs(s)>=obs-tol)/2**n
def holm(ps):
    m=len(ps); order=sorted(range(m),key=lambda i:ps[i]); adj=[0]*m; run=0
    for k,i in enumerate(order):
        run=max(run,min(1,(m-k)*ps[i])); adj[i]=run
    return adj
def tci(d):
    from statistics import mean, stdev
    n=len(d); m=mean(d); s=stdev(d) if n>1 else 0
    t={17:2.109816,19:2.093024}[n-1]
    return m, m-t*s/math.sqrt(n), m+t*s/math.sqrt(n), s
s4={(r['algorithm'],int(r['trial_seed'])):r for r in P if r['scenario']=='S4'}
s5={(r['algorithm'],int(r['trial_seed'])):r for r in S5}
algs=sorted(set(a for a,_ in s5)); seeds=sorted(set(s for _,s in s5))
print("seeds",seeds[:3],len(seeds))
# workload hash match S4 vs S5? primary has no hash column; check paired_workload_hashes
H=rd('data/primary/paired_workload_hashes_80.csv'); print("hash file cols",list(H[0].keys())[:8])
print("\n== S4->S5 paired change in completions per policy (S5 minus S4), exact sign-flip, Holm over 8 ==")
res=[]
for a in algs:
    d=[int(s5[(a,s)]['completed'])-int(s4[(a,s)]['completed']) for s in seeds]
    m,lo,hi,sd=tci(d); p=signflip_exact(d); res.append((a,m,lo,hi,p,sum(x<0 for x in d),sum(x==0 for x in d)))
adj=holm([r[4] for r in res])
for r,h in zip(res,adj): print(f"{r[0]:14s} mean {r[1]:+6.2f} CI[{r[2]:+.2f},{r[3]:+.2f}] p={r[4]:.3g} holm={h:.3g} worse/ties={r[5]}/{r[6]}")
d=[sum(int(s5[(a,s)]['completed']) for a in algs)-sum(int(s4[(a,s)]['completed']) for a in algs) for s in seeds]
print("fleet-of-8 pooled per-seed change: mean",st.mean(d)/8,"per policy-run; seeds declining",sum(x<0 for x in d),"/20; exact p",signflip_exact(d))
print("\n== Difference-in-differences vs Hungarian: (S5-S4)_policy - (S5-S4)_Hungarian ==")
res=[]
for a in algs:
    if a=='hungarian': continue
    d=[(int(s5[(a,s)]['completed'])-int(s4[(a,s)]['completed']))-(int(s5[('hungarian',s)]['completed'])-int(s4[('hungarian',s)]['completed'])) for s in seeds]
    m,lo,hi,sd=tci(d); res.append((a,m,lo,hi,signflip_exact(d)))
adj=holm([r[4] for r in res])
for r,h in zip(res,adj): print(f"{r[0]:14s} DiD {r[1]:+6.2f} CI[{r[2]:+.2f},{r[3]:+.2f}] p={r[4]:.3g} holm={h:.3g}")
print("\n== S5 energy per completion and battery ==")
for a in algs:
    b=sum(float(s5[(a,s)]['battery_Wh']) for s in seeds); c=sum(int(s5[(a,s)]['completed']) for s in seeds)
    b4=sum(float(s4[(a,s)]['battery_Wh']) for s in seeds); c4=sum(int(s4[(a,s)]['completed']) for s in seeds)
    print(f"{a:14s} S5 {b/20:8.1f} Wh/run {c} done {b/c:6.2f} Wh/compl | S4 {b4/20:8.1f} {c4} {b4/c4:6.2f}")
print("\n== Determinism check: ablation alpha1 means vs nominal runs on 18 non-pilot seeds ==")
inf={ (r['scenario'],r['algorithm']):r for r in rd('data/ablation/step110d_paired_inference.csv')}
for sc in ['S3','S4']:
  for a in ['hungarian','greedy']:
    v=[float(r['battery_Wh']) for r in P if r['scenario']==sc and r['algorithm']==a and int(r['trial_seed']) not in (1001,2001)]
    c=sum(int(r['completed']) for r in P if r['scenario']==sc and r['algorithm']==a and int(r['trial_seed']) not in (1001,2001))
    print(sc,a,"nominal18 mean",round(st.mean(v),4),"ablation alpha1 mean",inf[(sc,a)]['alpha1_mean_battery_Wh'],"nominal18 completed",c)
print("\n== Ablation sd of paired energy diffs and S4 per-seed completions ==")
for sc in ['S3','S4']:
  for a in ['hungarian','greedy']:
    d=[float(r['alpha1_minus_alpha0_battery_Wh']) for r in A if r['scenario']==sc and r['algorithm']==a]
    m,lo,hi,sd=tci(d); print(sc,a,f"mean {m:.2f} sd {sd:.1f} CI[{lo:.1f},{hi:.1f}] exact p {signflip_exact(d):.5f}")
print("\n== S4 nominal pickup/fulfil for Greedy seeds where incomplete ==")
for r in P:
    if r['scenario']=='S4' and int(r['completed'])<100: print(r['algorithm'],r['trial_seed'],r['completed'])
