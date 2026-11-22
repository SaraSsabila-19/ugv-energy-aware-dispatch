"""Offline audit, scientific design and synthetic analyzer tests; no fleet simulation."""
import tempfile, unittest, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import experiment_f as F
from calibrate_F import calculate

class FTests(unittest.TestCase):
    def setUp(self):self.p=F.protocol();self.inputs={'UTP':{'utp_graph.graphml':'g','hotspot_locations.csv':'h'}}
    def fake(self,sp):
        a=sp['alpha_energy'];s=sp['seed'];c=sp['config'];soc=sp['initial_soc'];pct={'LOW':1,'BASE':2,'HIGH':3}[c]+int(soc==.25)*2+(s%7000)/10000
        done=100-int(soc==.25)*3-a*int(c=='HIGH');b=1000*(1-a*pct/100)
        return dict(spec=sp,metrics=dict(battery_Wh=b,completed=done,wait_s=200+a,ride_s=300,Wh_per_completed=b/done,km=20,grid_Wh=40,energy_blocked_insertions=int(soc==.25)*2,corr_energy_ss=1,corr_time_ss=1,corr_cross=.997,energy_time_r=.997,assignment_energy_Wh=b),workload=str(s),od=[(i,i,i+1,480) for i in range(100)],arrivals=list(range(100)),fleet=[('1','P02',9000*soc)])
    def test_calibration(self):
        q,audit,tr,intervals=calculate();self.assertEqual(q['files'],35);self.assertEqual(q['rows'],14658);self.assertEqual(q['configs'],self.p['configs']);self.assertEqual(q['train_intervals'],254);self.assertEqual(q['holdout_intervals'],179);self.assertEqual(q['holdout_inside_training_range'],2);self.assertAlmostEqual(q['holdout_center_MAPE_pct'],19.6545905444644,places=6)
        self.assertEqual(len(intervals),433);self.assertEqual(len(set(r['center_pred_Wh'] for r in tr)),8)
    def test_matrix(self):
        pilot=F.matrix(self.p,True,self.inputs);main=F.matrix(self.p,False,self.inputs);self.assertEqual(len(pilot),24);self.assertEqual(len(main),960);self.assertTrue({s['seed'] for s in pilot}.isdisjoint(s['seed'] for s in main))
    def test_pair_rejection(self):
        specs=F.matrix(self.p,True,self.inputs);data={(s['seed'],s['config'],s['initial_soc'],s['algorithm'],s['alpha_energy']):self.fake(s) for s in specs}
        F.verify_pairs(data,self.p,self.p['pilot_seeds']);data[next(iter(data))]['workload']='wrong'
        with self.assertRaisesRegex(ValueError,'Workload'):F.verify_pairs(data,self.p,self.p['pilot_seeds'])
    def test_analysis(self):
        specs=F.matrix(self.p,False,self.inputs)
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)
            with patch.object(F,'inspect',side_effect=lambda out,sp,aud:self.fake(sp)):F.analyze(out,self.p,False,specs,None)
            cs=F.rows(out/'analysis/primary_contrasts.csv');self.assertEqual(len(cs),26)
            for c in cs:
                if c['family']=='interaction':self.assertAlmostEqual(float(c['mean']),-1 if c['contrast'].startswith('LOW') else 1 if c['contrast'].startswith('HIGH') else 2)
                elif c['contrast'].startswith('HIGH'):self.assertEqual(c['service_guard_met'],'False')
                else:self.assertEqual(c['service_guard_met'],'True')
            for name in ('campaign_identity.json','protocol.json','run_matrix.json'):F.write_json(out/name,{})
            z=F.export(out,self.p,False);self.assertTrue(z.exists())
    def test_pilot(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)
            with patch.object(F,'inspect',side_effect=lambda out,sp,aud:self.fake(sp)):F.analyze(out,self.p,True,F.matrix(self.p,True,self.inputs),None)
            self.assertFalse((out/'analysis/primary_contrasts.csv').exists());self.assertEqual(F.load_json(out/'validation_report.json')['validated'],24)
if __name__=='__main__':unittest.main()
