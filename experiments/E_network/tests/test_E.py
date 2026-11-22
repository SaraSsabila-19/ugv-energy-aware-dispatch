"""Offline design, pairing, inference, export tests; not a simulator test."""
import math, tempfile, unittest, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import experiment_e as E

class ETests(unittest.TestCase):
    def setUp(self):
        self.p=E.protocol(); self.inputs={n:{'utp_graph.graphml':'g','hotspot_locations.csv':'h','parking_registry.json':'p'} for n in self.p['networks']}
    def fake(self,sp):
        # Known true 1/2/3/4% effects with nonzero seed variation, for both solvers.
        a=sp['alpha_energy'];w=sp['window_s'];n=sp['network'];s=sp['seed']; pct=1+int(n=='UM_district')+2*int(w==600)+(s%7000)/10000
        return dict(spec=sp,metrics=dict(battery_Wh=1000*(1-a*pct/100),completed=100-a*int(n=='UM_district'),wait_s=200+a,ride_s=300,Wh_per_completed=10,km=20,grid_Wh=40,corr_energy_ss=1,corr_time_ss=1,corr_cross=.997,energy_time_r=.997,assignment_energy_Wh=1000*(1-a*pct/100)),workload=f'{s}|{n}|{w}',od=[(i,i,i+1,480) for i in range(100)],arrivals=[w*i/100 for i in range(100)],fleet=[('1','P02',9000)])
    def test_matrix(self):
        pilot=E.matrix(self.p,True,self.inputs); main=E.matrix(self.p,False,self.inputs)
        self.assertEqual(len(pilot),16);self.assertEqual(len(main),640);self.assertTrue({s['seed'] for s in pilot}.isdisjoint(s['seed'] for s in main))
    def test_pair_rejection(self):
        specs=E.matrix(self.p,True,self.inputs);data={(s['seed'],s['network'],s['window_s'],s['algorithm'],s['alpha_energy']):self.fake(s) for s in specs}
        E.verify_pairs(data,self.p,self.p['pilot_seeds']);data[next(iter(data))]['od']=[(0,1,2,480)]
        with self.assertRaisesRegex(ValueError,'Mapped OD'):E.verify_pairs(data,self.p,self.p['pilot_seeds'])
    def test_analysis(self):
        specs=E.matrix(self.p,False,self.inputs)
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)
            with patch.object(E,'inspect',side_effect=lambda out,sp,aud:self.fake(sp)):E.analyze(out,self.p,False,specs,None)
            cs=E.rows(out/'analysis/primary_contrasts.csv');self.assertEqual(len(cs),16)
            for c in cs:
                if c['family']=='interaction':self.assertAlmostEqual(float(c['mean']),1 if c['contrast'].startswith('UM') else 2)
                elif c['contrast'].startswith('UM'):self.assertEqual(c['service_guard_met'],'False')
                else:self.assertEqual(c['service_guard_met'],'True')
            for name in ('campaign_identity.json','protocol.json','run_matrix.json'):E.write_json(out/name,{})
            z=E.export(out,self.p,False);self.assertTrue(z.exists())
    def test_pilot(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)
            with patch.object(E,'inspect',side_effect=lambda out,sp,aud:self.fake(sp)):E.analyze(out,self.p,True,E.matrix(self.p,True,self.inputs),None)
            self.assertFalse((out/'analysis/primary_contrasts.csv').exists());self.assertEqual(E.load_json(out/'validation_report.json')['validated'],16)

if __name__=='__main__':unittest.main()
