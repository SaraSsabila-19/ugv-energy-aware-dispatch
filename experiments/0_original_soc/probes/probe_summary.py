"""Aggregate decision-sensitivity probes. usage: python probe_summary.py PROBE_OUT"""
import json, glob, os, sys, collections, csv
import numpy as np
out = sys.argv[1]
agg = collections.defaultdict(lambda: collections.Counter()); chg = collections.defaultdict(list); rs = collections.defaultdict(list)
check = []
for d in sorted(glob.glob(os.path.join(out, 'PR_*'))):
    f = d + '/probe_stats.json'
    if not os.path.exists(f): continue
    s = json.load(open(f)); lab = os.path.basename(d)
    a = lab.split('_')[1]; soc = lab.split('_soc')[1].split('_')[0]; al = lab.split('_a')[-1]
    k = (a, soc, al)
    for key in ('rounds', 'rounds_multi', 'rounds_differ', 'pairs_active', 'pairs_changed', 'rounds_card_differ', 'sel_pairs', 'sel_pairs_busy', 'sel_insertion_changed', 'n_finite_pairs'):
        agg[k][key] += s.get(key, 0) or 0
    agg[k]['runs'] += 1
    chg[k] += s.get('ins_changes', []); rs[k].append(s['pooled_pair_r_energy_time'])
    # verify probe run equals the confirmatory run for the same condition
    seed = lab.split('_seed')[1].split('_')[0]; soc_lbl = {'1.0': '100', '0.25': '25'}[soc]
    cf = glob.glob(f'/home/claude/conf_out/S4_{a}_seed{seed}_soc{soc_lbl}_a{al}/results/*/run_summary.csv')
    pf = glob.glob(d + '/results/*/run_summary.csv')
    if cf and pf:
        x = next(csv.DictReader(open(cf[0]))); y = next(csv.DictReader(open(pf[0])))
        check.append(all(x[c] == y[c] for c in ('completed_requests', 'total_battery_withdrawn_Wh', 'total_distance_km')))
print(f'probe runs identical to confirmatory runs: {sum(check)}/{len(check)}')
print('policy soc alpha | runs | dispatch rounds | rounds where the other alpha picks a different matching | selected pairs | pairs whose vehicle-request match changes | insertion order changes (of selected pairs) | of busy-vehicle pairs | mean dE, dT of changed insertions (active - alt) | pooled pair r')
for k in sorted(agg):
    g = agg[k]; c = np.array(chg[k]) if chg[k] else np.zeros((0, 2))
    print(f"{k} | {g['runs']} | {g['rounds']} | {g['rounds_differ']} ({100*g['rounds_differ']/max(1,g['rounds']):.1f}%) | {g['sel_pairs']} | {g['pairs_changed']} ({100*g['pairs_changed']/max(1,g['pairs_active']):.1f}%) | {g['sel_insertion_changed']} ({100*g['sel_insertion_changed']/max(1,g['sel_pairs']):.1f}%) | {100*g['sel_insertion_changed']/max(1,g['sel_pairs_busy']):.1f}% of {g['sel_pairs_busy']} | {c[:,0].mean() if len(c) else float('nan'):+.2f} Wh, {c[:,1].mean() if len(c) else float('nan'):+.2f} s | {np.mean(rs[k]):.4f}")
tot = collections.Counter()
for g in agg.values(): tot.update(g)
print(f"ALL: matching changed in {tot['rounds_differ']}/{tot['rounds']} rounds ({100*tot['rounds_differ']/tot['rounds']:.1f}%), {tot['pairs_changed']}/{tot['pairs_active']} pairs; insertion order changed for {tot['sel_insertion_changed']}/{tot['sel_pairs']} selected pairs ({100*tot['sel_insertion_changed']/tot['sel_pairs']:.1f}%)")
