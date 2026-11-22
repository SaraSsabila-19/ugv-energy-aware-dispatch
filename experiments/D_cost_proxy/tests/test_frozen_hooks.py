"""Execute exact frozen predictor, insertion evaluator and solvers on a controlled graph fixture."""
import ast
import copy
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Tuple
import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ugvkit.d_runner import install,coefficients,proxy_energy
from ugvkit.common import sha256_file
from ugvkit import FROZEN_APP_SHA256
import experiment_d as D

@dataclass
class PassengerStop:
    kind:str
    request_id:int
    node:int

def fixture(source,mass,mp,alg):
    tree=ast.parse(source.read_text()); functions={'assignment_cost_terms','stop_plan_masses','assign_greedy','assign_hungarian','validate_assignment_pairs'}
    methods={'_predict','pair_cost','_dwell','eligible','_wait_diagnostics'}
    engine=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SharedRideEngine');engine.body=[n for n in engine.body if isinstance(n,ast.FunctionDef) and n.name in methods]
    t=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in functions]+[engine],type_ignores=[])
    b=dict(math=math,np=np,linear_sum_assignment=linear_sum_assignment,PassengerStop=PassengerStop,Mover=NS,Tuple=Tuple,
           UGV_EMPTY_MASS_KG=mass,UGV_PASSENGER_MASS_KG=mp,UGV_PASSENGER_CAPACITY=6,UGV_G=9.81,UGV_C_RR=.012,UGV_RHO=1.23,UGV_C_D=.50,UGV_A=2.,UGV_ETA=.9,UGV_DRIVING_AUX_POWER_W=50.,UGV_V_MAX=22/3.6,
           BOARDING_DWELL_S=10.,ALIGHTING_DWELL_S=5.,DWELL_AUX_POWER_W=50.,MAX_RIDE_FACTOR=2.,MAX_EXTRA_RIDE_S=300.,BATTERY_CAPACITY_WH=9000.,BATTERY_RESERVE_FRACTION=.2,SOC_COST_WEIGHT=0.,ASSIGNMENT_COST_MODE='normalized',COST_ENERGY_REFERENCE_WH=100.,COST_TIME_REFERENCE_S=600.)
    exec(compile(ast.fix_missing_locations(t),str(source),'exec'),b)
    b.update(G=NS(nodes={i:dict(x=0,y=0) for i in range(12)}),haversine=lambda *x:0.,simulation_time_s=lambda:0.,pickup_deadline_exceeded=lambda *x:False,vehicle_home_node=lambda m:0,RUN={'request_records':{i:{} for i in range(10)}})
    app=NS(**b);app.ALGO_FUNCS={k:b['assign_'+k] for k in ('greedy','hungarian')}
    def leg(self,src,dst,m):
        d=abs(src-dst)*120.;c=coefficients(self.b);return NS(distance=d,mass=m,duration=d/self.b.UGV_V_MAX+(3. if d else 0.),energy=(c['e0_Wh_km']+c['e1_Wh_passenger_km']*(m-mass)/mp)*d/1000+(m/2000 if d else 0.))
    app.SharedRideEngine._leg=leg
    e=app.SharedRideEngine();e.b=app;e.states={};e.active={};e.direct_time={0:150.};e.ride_deadline={};e.wait_diagnostic_stats={};e.energy_blocked_pairs=set()
    for key in ('pair_evaluations','non_energy_feasible_insertions','energy_blocked_insertions','energy_blocked_pair_evaluations','feasible_pair_evaluations'):setattr(e,key,0)
    movers=[NS(id=1,node=1,planned_stops=[],onboard_request_ids=[],passengers_onboard=0,soc_Wh=9000.),NS(id=2,node=2,planned_stops=[PassengerStop('pickup',0,4),PassengerStop('dropoff',0,8)],onboard_request_ids=[],passengers_onboard=0,soc_Wh=9000.)]
    e.states[1]=NS(leg=None,target=None);e.states[2]=NS(leg=e._leg(2,4,mass),target=movers[1].planned_stops[0],leg_elapsed=1.,leg_energy=0.,dwell_remaining=None);e.active={1:set(),2:{0}}
    return app,e,movers,[NS(id=1,pickup_node=3,drop_node=9),NS(id=2,pickup_node=5,drop_node=10)]

def run(source,mass,mp,alg,arm,alpha,hook):
    app,e,ms,rs=fixture(source,mass,mp,alg)
    observer=install(app,np,dict(algorithm=alg,arm=arm,alpha_energy=alpha)) if hook else None
    C=np.full((2,2),np.inf);meta={}
    for i,m in enumerate(ms):
        for j,r in enumerate(rs):C[i,j],meta[i,j]=e.pair_cost(m,r,alpha,1.)
    pairs=app.ALGO_FUNCS[alg](C);app.validate_assignment_pairs(C,pairs)
    if observer:
        d=observer.result();assert d['candidate_count']==e.non_energy_feasible_insertions-e.energy_blocked_insertions
        assert len(d['rounds'])==1;rr=d['rounds'][0];assert rr['active_pairs']==len(pairs)
        assert math.isclose(rr['active_energy_Wh'],sum(meta[i,j]['delta_energy'] for i,j in pairs));assert d['residual_abs_sum_Wh']>0
        # The diagnostic path outside insertion must retain its native terms.
        assert app.assignment_cost_terms(100,600,1,alpha,1,0)==(alpha,1.,0.)
    return C,pairs,meta

if __name__=='__main__':
    source=Path(sys.argv[1]);assert sha256_file(source)==FROZEN_APP_SHA256
    for mass,mp in ((825,80),(455.8,100)):
        for alg in ('greedy','hungarian'):
            for arm,alpha in D.protocol(False)['arms'].items():
                C,pairs,meta=run(source,mass,mp,alg,arm,alpha,True)
                if arm!='pk1':
                    C0,p0,m0=run(source,mass,mp,alg,arm,alpha,False);assert np.array_equal(C,C0) and pairs==p0 and meta==m0
    assert len(D.matrix(D.protocol(True)))==36 and len(D.matrix(D.protocol(False)))==1120
    a=coefficients(NS(UGV_V_MAX=22/3.6,UGV_G=9.81,UGV_C_RR=.012,UGV_RHO=1.23,UGV_C_D=.5,UGV_A=2.,UGV_ETA=.9,UGV_DRIVING_AUX_POWER_W=50.,UGV_EMPTY_MASS_KG=825,UGV_PASSENGER_MASS_KG=80))
    assert proxy_energy(a,0,-1)<0
    print('PASS: frozen insertion evaluator, committed-leg capture, native matrices, true energy accounting, both solvers, 28 arm fixtures; 24 native comparisons; protocol counts')
