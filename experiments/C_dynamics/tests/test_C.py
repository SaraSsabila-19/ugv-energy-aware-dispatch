import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from ugvkit.impulse_runner import install, alpha_for
from experiment_c import target_check, end_equal, protocol, references, spec, analyze


def fake(mode,k):
    class Engine:
        def pair_cost(self,m,r,alpha,beta):
            e=10 if m.id==r.id else 5
            t=1 if m.id==r.id else 2
            return t+alpha*e, {'stops':[('pickup',r.id),('dropoff',r.id)],'delta_energy':e,'delta_time':t}
    def choose(C):
        return [(0,0),(1,1)] if C[0,0]<C[0,1] else [(0,1),(1,0)]
    app=SimpleNamespace(SharedRideEngine=Engine,ALGO_FUNCS={'greedy':choose})
    trace=install(app,np,mode,k,'greedy'); e=Engine()
    for _ in range(3):
        C=np.asarray([[e.pair_cost(SimpleNamespace(id=i,planned_stops=[]),SimpleNamespace(id=j),0,1)[0] for j in range(2)] for i in range(2)])
        app.ALGO_FUNCS['greedy'](C)
    rounds=trace.result()['rounds']
    for r in rounds: r['tick']=r['round']*100; r['time_s']=r['tick']*.3
    total=sum(a['energy_Wh'] for r in rounds for a in r['actions'])
    return dict(trace=rounds,metrics={'battery_Wh':total},semantic=str(total),spec={'label':mode+str(k)})


class TestC(unittest.TestCase):
    def test_schedules(self):
        self.assertEqual([alpha_for('pulse',2,r) for r in range(1,5)],[0,1,0,0])
        self.assertEqual([alpha_for('prefix',2,r) for r in range(1,5)],[1,1,0,0])
        self.assertEqual([alpha_for('on',0,r) for r in range(1,5)],[1,1,1,1])

    def test_pair_and_endpoint(self):
        off,on=fake('off',0),fake('on',0)
        previous=off; deltas=[]; pulses=[]
        for k in range(1,4):
            pulse=fake('pulse',k); target_check(off,pulse,k)
            pulses.append(off['metrics']['battery_Wh']-pulse['metrics']['battery_Wh'])
            current=fake('prefix',k); target_check(previous,current,k)
            deltas.append(previous['metrics']['battery_Wh']-current['metrics']['battery_Wh']); previous=current
        end_equal(previous,on); self.assertEqual(previous['trace'],on['trace'])
        self.assertEqual(sum(deltas),30); self.assertEqual(sum(pulses),30)

    def test_reject_tamper(self):
        x,y=fake('off',0),fake('pulse',2); y['trace'][0]['state']='tamper'
        with self.assertRaises(ValueError): target_check(x,y,2)
        y=fake('pulse',2); y['trace'][1]['feasibility']='tamper'
        with self.assertRaises(ValueError): target_check(x,y,2)

    def test_reject_incomplete_matrix(self):
        class E:
            def pair_cost(self,*args): return 1,{}
        app=SimpleNamespace(SharedRideEngine=E,ALGO_FUNCS={'greedy':lambda C:[]})
        install(app,np,'off',0,'greedy')
        with self.assertRaises(RuntimeError): app.ALGO_FUNCS['greedy'](np.ones((2,2)))

    def test_infeasible_round_does_not_advance(self):
        class E:
            def pair_cost(self,m,r,alpha,beta):
                return (float('inf'),None) if r.id==0 else (alpha,{'stops':[], 'delta_energy':1,'delta_time':1})
        app=SimpleNamespace(SharedRideEngine=E,ALGO_FUNCS={'greedy':lambda C: [] if not np.isfinite(C).any() else [(0,0)]})
        t=install(app,np,'pulse',1,'greedy'); eng=E(); m=SimpleNamespace(id=1,planned_stops=[])
        # First all-infeasible matrix was never sent to solver.
        eng.pair_cost(m,SimpleNamespace(id=0),0,1)
        for _ in range(2):
            c,_=eng.pair_cost(m,SimpleNamespace(id=1),0,1); app.ALGO_FUNCS['greedy'](np.array([[c]]))
        self.assertEqual([r['alpha'] for r in t.result()['rounds']],[1,0])

    def test_protocol(self):
        p=protocol(False); q=protocol(True)
        self.assertEqual(len(p['seeds']),40); self.assertFalse(set(p['seeds'])&set(q['seeds']))
        self.assertEqual(len(references(p)),160); self.assertEqual(len(references(q)),8)
        self.assertEqual(spec(p,p['seeds'][0],'greedy','prefix',1)['alpha_energy'],0)

    def test_analysis_pipeline(self):
        def mock_inspect(out,sp):
            result=fake(sp['mode'].replace('control_',''),sp['k'])
            result['spec']=sp; result['workload']='matched'; result['fleet']=['same']
            result['metrics'].update({k:0.0 for k in ('km','empty_pickup_km','return_km','productive_km','passenger_km','wait_s','ride_s','completed','grid_Wh')})
            if sp['mode'].startswith('control_'): result['trace']=[]
            return result
        with tempfile.TemporaryDirectory() as tmp, patch('experiment_c.inspect',mock_inspect):
            out=Path(tmp); analyze(out,protocol(True),[])
            for name in ('seed_effects.csv','response_horizons.csv','primary_contrasts.csv','impulse_prefix.png','response_horizons.pdf'):
                self.assertTrue((out/'analysis'/name).is_file())
            self.assertTrue((out/'validation_report.json').is_file())


if __name__=='__main__': unittest.main(verbosity=2)
