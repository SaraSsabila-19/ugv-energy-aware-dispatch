"""Write the run list for the S4 energy-weight x initial-SOC experiment.
usage: python make_matrix.py --seeds 21001:60001:1000 > runs.txt
Each line: LABEL ALGO TRIAL_INDEX SOC ALPHA EXTRA_SEEDS_CSV
Trial indices 0-19 are the frozen seeds 1001..20001; new seeds get indices 20, 21, ...
"""
import argparse
p=argparse.ArgumentParser(); p.add_argument('--seeds',required=True,help='start:stop:step (inclusive) or comma list')
a=p.parse_args()
if ':' in a.seeds:
    s0,s1,st=map(int,a.seeds.split(':')); seeds=list(range(s0,s1+1,st))
else: seeds=[int(x) for x in a.seeds.split(',')]
FROZEN=[1001+1000*i for i in range(20)]; PILOT={91001,92001,93001,94001,99001}  # pilot + smoke-test seeds from the review
bad=[s for s in seeds if s in FROZEN or s in PILOT]
if bad: raise SystemExit(f'Refusing seeds already used for campaigns, SOC selection or the pilot: {bad}')
ex=','.join(map(str,seeds))
for i,s in enumerate(seeds):
    t=20+i
    for alg in ('hungarian','greedy'):
        for soc in ('1.0','0.25'):
            for al in ('0','1'):
                print(f'S4_{alg}_seed{s}_soc{int(float(soc)*100)}_a{al} {alg} {t} {soc} {al} {ex}')
