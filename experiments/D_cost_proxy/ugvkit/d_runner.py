"""Experiment D: rank feasible insertions using native costs or a physical surrogate.

The frozen pair_cost function performs every feasibility/reserve check and chooses
the insertion. Only its assignment_cost_terms call is intercepted, in scope.
Original predictors, paths, activation, battery physics and solvers are retained.
"""
import json
import math
import sys
from pathlib import Path
from ugvkit import runner
from ugvkit.impulse_runner import digest


def coefficients(b):
    v=b.UGV_V_MAX
    e0=(b.UGV_EMPTY_MASS_KG*b.UGV_G*b.UGV_C_RR+0.5*b.UGV_RHO*b.UGV_C_D*b.UGV_A*v*v)/b.UGV_ETA*1000/3600 + b.UGV_DRIVING_AUX_POWER_W*1000/v/3600
    e1=b.UGV_PASSENGER_MASS_KG*b.UGV_G*b.UGV_C_RR/b.UGV_ETA*1000/3600
    kappa=e0*v/1000
    return dict(e0_Wh_km=e0,e1_Wh_passenger_km=e1,kappa_Wh_s=kappa,
                lambda_s_passenger_km=(e1/100)/(1/600+kappa/100),v_m_s=v)


def proxy_energy(coef, delta_t, delta_pk):
    return coef['kappa_Wh_s']*delta_t+coef['e1_Wh_passenger_km']*delta_pk


def features(legs, b):
    # The committed first leg is common to baseline and every legal insertion;
    # the frozen _predict does not call _leg for it, so it cancels in deltas.
    d=math.fsum(float(l.distance)/1000 for l in legs)
    pk=math.fsum(float(l.distance)/1000*((float(l.mass)-b.UGV_EMPTY_MASS_KG)/b.UGV_PASSENGER_MASS_KG) for l in legs)
    return d,pk


class Observer:
    def __init__(self, app, spec):
        self.app,self.spec=app,spec
        self.context=None; self.capture=None; self.pending=[]; self.rounds=[]
        self.count=0;self.res_abs=0.;self.res_sq=0.;self.res_sum=0.;self.dist_res_abs=0.;self.e_abs=0.;self.clipped_negative_proxy=0
        self.coeff=None

    def result(self):
        if any(math.isfinite(x[0]) for x in self.pending): raise RuntimeError('Unsolved finite pair')
        return dict(schema=1,arm=self.spec['arm'],alpha=self.spec['alpha_energy'],coefficients=self.coeff,
                    candidate_count=self.count,residual_abs_sum_Wh=self.res_abs,residual_square_sum_Wh2=self.res_sq,
                    residual_signed_sum_Wh=self.res_sum,distance_residual_abs_sum_Wh=self.dist_res_abs,
                    candidate_energy_abs_sum_Wh=self.e_abs,negative_surrogate_energy_count=self.clipped_negative_proxy,
                    rounds=self.rounds)


def install(app,np,spec):
    o=Observer(app,spec); E=app.SharedRideEngine
    orig_pair,orig_predict,orig_leg,orig_terms=E.pair_cost,E._predict,E._leg,app.assignment_cost_terms
    alpha_expected=float(spec['alpha_energy']); surrogate=spec['arm']=='pk1'

    def leg(self,*args,**kwargs):
        x=orig_leg(self,*args,**kwargs)
        if o.capture is not None: o.capture.append(x)
        return x

    def predict(self,m,stops):
        if o.context is None: return orig_predict(self,m,stops)
        if o.capture is not None: raise RuntimeError('Nested prediction unexpectedly')
        o.capture=[]
        try:
            x=orig_predict(self,m,stops); legs=o.capture
        finally: o.capture=None
        if x is not None:
            skipped=int(bool(stops) and self.states[m.id].leg is not None)
            if len(legs)!=len(stops)+1-skipped or any(l is None for l in legs): raise RuntimeError('Prediction leg capture mismatch')
            d,pk=features(legs,self.b)
            data=dict(pred=x,d=d,pk=pk,stops=digest(tuple(stops)))
            if o.context['baseline'] is None: o.context['baseline']=data
            o.context['latest']=data
        return x

    def terms(delta_energy_wh,delta_time_s,soc_fraction,alpha,beta,gamma):
        vals=orig_terms(delta_energy_wh,delta_time_s,soc_fraction,alpha,beta,gamma)
        c=o.context
        if c is None: return vals # includes frozen reporting diagnostics outside pair_cost
        if alpha!=alpha_expected or beta!=1 or gamma!=0 or app.ASSIGNMENT_COST_MODE!='normalized' or app.COST_TIME_REFERENCE_S!=600 or app.COST_ENERGY_REFERENCE_WH!=100:
            raise RuntimeError('Unexpected cost settings')
        old,new=c['baseline'],c['latest']
        if old is None or new is None or old is new: raise RuntimeError('Missing baseline or insertion features')
        de,dt=float(delta_energy_wh),float(delta_time_s)
        if not (math.isclose(de,max(0.,new['pred']['energy']-old['pred']['energy']),abs_tol=1e-10) and math.isclose(dt,max(0.,new['pred']['duration']-old['pred']['duration']),abs_tol=1e-10)):
            raise RuntimeError('Candidate energy/time not aligned with original predictor')
        d,pk=new['d']-old['d'],new['pk']-old['pk']; coef=o.coeff
        pe=proxy_energy(coef,dt,pk); re=de-pe; dre=de-coef['e0_Wh_km']*d-coef['e1_Wh_passenger_km']*pk
        o.count+=1;o.res_abs+=abs(re);o.res_sq+=re*re;o.res_sum+=re;o.dist_res_abs+=abs(dre);o.e_abs+=abs(de);o.clipped_negative_proxy+=int(pe<0)
        cf=de/100+dt/600; cp=pe/100+dt/600
        if surrogate: vals=(alpha*pe/100,vals[1],vals[2])
        active=sum(vals); idx=c['count']; c['count']+=1
        cand=dict(energy=de,time=dt,pk=pk,d=d,residual=re,stops=new['stops'],pickup=float(new['pred']['pickups'][c['rid']]))
        for name,cost in [('full',cf),('proxy',cp),('active',active)]:
            rank=(cost,cand['pickup'],idx)
            if c[name] is None or rank<c[name][0]: c[name]=(rank,cand)
        return vals

    def pair(self,m,request,alpha,beta):
        if o.context is not None: raise RuntimeError('Nested pair cost')
        if o.coeff is None: o.coeff=coefficients(self.b)
        c=dict(rid=request.id,baseline=None,latest=None,full=None,proxy=None,active=None,count=0)
        o.context=c
        try: cost,meta=orig_pair(self,m,request,alpha,beta)
        finally: o.context=None
        if math.isfinite(cost):
            if c['active'] is None or not math.isclose(cost,c['active'][0][0],abs_tol=1e-12) or digest(meta['stops'])!=c['active'][1]['stops']:
                raise RuntimeError('Frozen selected insertion does not match observed active ranking')
            f,p=c['full'][1],c['proxy'][1]
            regret=(p['energy']-f['energy'])/100+(p['time']-f['time'])/600
            bound=(p['residual']-f['residual'])/100
            if regret < -1e-10 or regret > bound+1e-10: raise RuntimeError('Pair-level surrogate regret bound violated')
        elif c['active'] is not None: raise RuntimeError('Feasible insertion lost')
        o.pending.append((float(cost),c['full'],c['proxy'],c['active'],m.id,request.id))
        return cost,meta

    app.assignment_cost_terms=terms; E._predict=predict; E._leg=leg; E.pair_cost=pair
    fn=app.ALGO_FUNCS[spec['algorithm']]

    def solve(C,*args,**kwargs):
        M=np.asarray(C,dtype=float); n=M.size
        if M.ndim!=2 or not n or len(o.pending)<n or any(math.isfinite(x[0]) for x in o.pending[:-n]): raise RuntimeError('Unaligned matrix')
        items=o.pending[-n:];o.pending=[]
        if not np.allclose(M,np.asarray([x[0] for x in items]).reshape(M.shape),equal_nan=True,rtol=1e-12,atol=1e-12): raise RuntimeError('Matrix order mismatch')
        F=np.asarray([x[1][0][0] if x[1] else math.inf for x in items]).reshape(M.shape)
        P=np.asarray([x[2][0][0] if x[2] else math.inf for x in items]).reshape(M.shape)
        if not np.array_equal(np.isfinite(F),np.isfinite(P)) or not np.array_equal(np.isfinite(F),np.isfinite(M)): raise RuntimeError('Different feasibility masks')
        active=fn(C,*args,**kwargs); full=fn(F); proxy=fn(P)
        def result(pairs,index):
            a=[]
            for i,j in sorted(map(tuple,pairs)):
                x=items[i*M.shape[1]+j]; c=x[index][1]; a.append((x[4],x[5],c))
            return a
        aa,ff,pp=result(active,3),result(full,1),result(proxy,2)
        key=lambda acts:[(x,y,c['stops']) for x,y,c in acts]
        if spec['arm'] in ('e1','pk1') and key(aa)!=key(ff if spec['arm']=='e1' else pp): raise RuntimeError('Active solver disagrees with reconstructed objective')
        def sumval(acts,k):return math.fsum(c[k] for _,_,c in acts)
        regret=(sumval(pp,'energy')-sumval(ff,'energy'))/100+(sumval(pp,'time')-sumval(ff,'time'))/600
        bound=(sumval(pp,'residual')-sumval(ff,'residual'))/100
        if spec['algorithm']=='hungarian' and (len(ff)!=len(pp) or regret < -1e-9 or regret > bound+1e-9): raise RuntimeError('Hungarian surrogate objective regret bound violated')
        o.rounds.append(dict(round=len(o.rounds)+1,shape=list(M.shape),active_pairs=len(aa),full_pairs=len(ff),proxy_pairs=len(pp),
            active_energy_Wh=sumval(aa,'energy'),full_energy_Wh=sumval(ff,'energy'),proxy_energy_Wh=sumval(pp,'energy'),
            full_time_s=sumval(ff,'time'),proxy_time_s=sumval(pp,'time'),full_pk_km=sumval(ff,'pk'),proxy_pk_km=sumval(pp,'pk'),
            full_action_sha256=digest(key(ff)),proxy_action_sha256=digest(key(pp)),active_action_sha256=digest(key(aa)),
            same_action=key(ff)==key(pp),same_matching=[x[:2] for x in ff]==[x[:2] for x in pp],native_objective_regret=regret,residual_difference_bound=bound,
            feasible_pairs=int(np.isfinite(M).sum()),pair_insertion_disagreements=sum(x[1] is not None and x[1][1]['stops']!=x[2][1]['stops'] for x in items)))
        return active

    solve.__name__=fn.__name__;app.ALGO_FUNCS[spec['algorithm']]=solve
    return o


def main():
    rd=Path(sys.argv[sys.argv.index('--run-dir')+1]); spec=json.loads((rd/'run_spec.json').read_text())
    if spec['probe']['enabled']: runner.install_probe=lambda app,np,ignored:install(app,np,spec)
    runner.main()


if __name__=='__main__': main()
