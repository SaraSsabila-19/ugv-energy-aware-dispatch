"""Exercise pilot and confirmatory analysis/export with artificial, not simulation, records."""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import experiment_d as D
from ugvkit.d_runner import coefficients
from ugvkit.common import write_json

def fake_inspect(out,sp):
    seed=sp['seed'];alpha=sp['alpha_energy'];a=sp['arm'].removeprefix('control_')
    m=sp['empty_mass'];mp=sp['passenger_mass'];bat=6000-50*alpha+(seed%17)
    c=coefficients(NS(UGV_V_MAX=22/3.6,UGV_G=9.81,UGV_C_RR=.012,UGV_RHO=1.23,UGV_C_D=.50,UGV_A=2.,UGV_ETA=.9,UGV_DRIVING_AUX_POWER_W=50.,UGV_EMPTY_MASS_KG=m,UGV_PASSENGER_MASS_KG=mp))
    r=dict(round=1,shape=[1,1],active_pairs=1,full_pairs=1,proxy_pairs=1,active_energy_Wh=bat,full_energy_Wh=50.,proxy_energy_Wh=51.,full_time_s=100.,proxy_time_s=99.,full_pk_km=1.,proxy_pk_km=1.,full_action_sha256='f',proxy_action_sha256='p',active_action_sha256='f',same_action=False,same_matching=True,feasible_pairs=1,pair_insertion_disagreements=1,native_objective_regret=.01,residual_difference_bound=.02,tick=1,time_s=1.)
    trace=[r] if sp['probe']['enabled'] else [];pr=dict(candidate_count=1,coefficients=c,residual_abs_sum_Wh=1.,residual_square_sum_Wh2=1.,residual_signed_sum_Wh=1.,candidate_energy_abs_sum_Wh=50.,distance_residual_abs_sum_Wh=1.,negative_surrogate_energy_count=0) if trace else None
    return dict(spec=sp,metrics=dict(battery_Wh=bat,km=100.,wait_s=280.,ride_s=100.,completed=100.,grid_Wh=1000.,duration_s=2700.,passenger_km=80.,passenger_km_per_productive_km=1.2),trace=trace,probe=pr,semantic=a,workload=str(seed),fleet=[str(seed)])

if __name__=='__main__':
    D.S.inspect=fake_inspect
    with tempfile.TemporaryDirectory() as t:
        for pilot in (True,False):
            out=Path(t)/str(pilot);out.mkdir();p=D.protocol(pilot);sp=D.matrix(p)
            D.analyze(out,p,sp)
            report=D.load_json(out/'validation_report.json');assert report['status']=='PASS' and report['validated']==len(sp)
            if not pilot:
                rows=D.S.rows(out/'analysis'/'primary_contrasts.csv');assert len(rows)==40 and sum(r['family']=='equivalence' for r in rows)==16
                assert all(float(r['holm_p'])==0 for r in rows if r['family']=='equivalence')
            for f,val in [('campaign_identity.json',{}),('protocol.json',p),('run_matrix.json',sp)]:write_json(out/f,val)
            assert D.S.export(out,p).exists()
    print('PASS: synthetic 36-run pilot and 1120-run confirmatory analysis, 40 contrasts, figures, checksum exports')
