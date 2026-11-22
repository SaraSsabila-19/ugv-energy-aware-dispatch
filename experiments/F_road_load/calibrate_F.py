"""Reproducible external vehicle diagnostic and empirical sensitivity anchors.

This is not calibration of the GMTLSV. DC-link gross draw, not pack-wide net
draw; near-flat stable-speed samples only. Keep repetitions separate.
"""
import csv, hashlib, json, math, re, statistics, zipfile
from pathlib import Path
from datetime import datetime
import numpy as np
from scipy.optimize import brentq

ROOT=Path(__file__).resolve().parent
CAL=ROOT/'calibration'
DATA=CAL/'ESOGU-ML5EV-v1.0.0.zip'
SHA='599d0f37d991b4d86f54c6e55137edbcebe691cdb0a893ce675442dd08adc8f9'
def require(x,msg):
    if not x: raise ValueError(msg)
def csvout(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def calculate():
    require(hashlib.sha256(DATA.read_bytes()).hexdigest()==SHA,'Source archive mismatch')
    audit=[]; sample=[]; digests={}; records=[]
    with zipfile.ZipFile(DATA) as z:
        require(z.testzip() is None,'Archive integrity failure')
        names=sorted(n for n in z.namelist() if n.endswith('.csv'));require(len(names)==35,'Expected 35 files')
        for n in names:digests.setdefault(hashlib.sha256(z.read(n)).hexdigest(),[]).append(Path(n).name)
        for n in names:
            name=Path(n).stem;b=z.read(n);sha=hashlib.sha256(b).hexdigest();raw=list(csv.DictReader(b.decode('utf-8-sig').splitlines()))
            m=re.fullmatch(r'(15|25|35)([LU])([CM])([SW])([12]?)',name);require(m is not None,'Unexpected run label')
            def parse(s):
                try:return datetime.fromisoformat(s)
                except ValueError:return datetime.strptime(s,'%m/%d/%Y %H:%M')
            speed,load,direction,season,rep=m.groups(); ts=[parse(r['Time_Stamp']) for r in raw];t=np.array([(x-ts[0]).total_seconds() for x in ts]); dt=np.diff(t)
            def arr(k):return np.array([float(r[k]) if r.get(k) else np.nan for r in raw])
            v=arr('vehicle_speed')/3.6;volts=arr('DC_Link_Voltage'); amps=arr('DC_Link_Current');power=volts*amps;slope=arr('slope')
            good=(dt==1)&np.isfinite(v[:-1])&np.isfinite(v[1:])&np.isfinite(power[:-1])&np.isfinite(power[1:])&(v[:-1]>=0)&(v[1:]>=0)
            mid=(v[:-1]+v[1:])/2; accel=v[1:]-v[:-1];gross=(np.maximum(power[:-1],0)+np.maximum(power[1:],0))/2; net=(power[:-1]+power[1:])/2
            slope_ok=(slope[:-1]==0)&(slope[1:]==0)
            eligible=good&slope_ok&(v[:-1]>=10/3.6)&(v[1:]>=10/3.6)&(v[:-1]<=22/3.6)&(v[1:]<=22/3.6)&(np.abs(accel)<=.25)
            duplicate=len(digests[sha])>1; split='train' if speed=='15' and season=='W' and rep=='1' else 'holdout' if speed=='15' and season=='W' and rep=='2' else 'excluded'
            if duplicate:split='excluded_duplicate'
            # All eight declared 15 km/h winter trips are retained; isolate valid consecutive intervals.
            if split in ('train','holdout'):
                require(int(eligible.sum())>=20 and np.sum(mid[eligible])>=50,'Insufficient near-flat qualifying exposure')
                # Published cargo increment 300 kg; manufacturer 700kg + assumed 75kg driver.
                # Unmeasured driver mass tested at 50 and 100kg as a separate sensitivity.
                vv=mid[eligible];aa=accel[eligible];yy=gross[eligible];distance=float(vv.sum()); measured=float(yy.sum()/3600)
                def pred(c,driver=75,vv=vv,aa=aa,load=load):
                    mass=700+driver+300*(load=='L')
                    return float(np.sum((np.maximum(0,mass*9.81*c+.615*vv*vv+1.2*mass*aa)*vv/.90+50)/3600))
                def estimate(driver=75):return float(brentq(lambda c:pred(c,driver)-measured,0,.10))
                rec=dict(file=name,split=split,load=load,direction=direction,intervals=int(eligible.sum()),distance_m=distance,measured_gross_Wh=measured,measured_Wh_km=1000*measured/distance,baseline_pred_Wh=pred(.012),effective_Crr=estimate(),effective_Crr_driver50=estimate(50),effective_Crr_driver100=estimate(100))
                records.append((rec,pred));sample.extend(dict(file=name,split=split,time=raw[i+1]['Time_Stamp'],speed_m_s=float(mid[i]),acceleration_m_s2=float(accel[i]),gross_DC_W=float(gross[i])) for i in np.flatnonzero(eligible))
            audit.append(dict(file=name,sha256=sha,rows=len(raw),non_one_second_intervals=int(np.sum(dt!=1)),negative_current_rows=int(np.sum(amps<0)),slope_available=bool(np.isfinite(slope).any()),duplicate_group=';'.join(digests[sha]) if duplicate else '',valid_distance_km=float(np.sum(mid[good])/1000),gross_DC_Wh=float(np.sum(gross[good])/3600),net_DC_Wh=float(np.sum(net[good])/3600),eligible_intervals=int(eligible.sum()),split=split))
    tr=[r for r,_ in records if r['split']=='train'];ho=[r for r,_ in records if r['split']=='holdout'];require(len(tr)==len(ho)==4,'Split mismatch')
    center=statistics.mean(r['effective_Crr'] for r in tr);low=math.floor(min(r['effective_Crr'] for r in tr)*1000)/1000;high=math.ceil(max(r['effective_Crr'] for r in tr)*1000)/1000
    for r,pred in records:
        for key,c in [('center',center),('low',low),('high',high)]:r[key+'_pred_Wh']=pred(c)
        for key in ('baseline','center','low','high'):r[key+'_error_pct']=100*(r[key+'_pred_Wh']-r['measured_gross_Wh'])/r['measured_gross_Wh']
    summary=dict(source_sha256=SHA,files=len(audit),rows=sum(r['rows'] for r in audit),duplicate_groups=[ns for ns in digests.values() if len(ns)>1],train_files=[r['file'] for r in tr],holdout_files=[r['file'] for r in ho],train_intervals=sum(r['intervals'] for r in tr),holdout_intervals=sum(r['intervals'] for r in ho),fit_center=center,configs=dict(LOW=low,BASE=.012,HIGH=high),holdout_baseline_MAPE_pct=statistics.mean(abs(r['baseline_error_pct']) for r in ho),holdout_center_MAPE_pct=statistics.mean(abs(r['center_error_pct']) for r in ho),holdout_inside_training_range=sum(low<=r['effective_Crr']<=high for r in ho),train_coefficients=[r['effective_Crr'] for r in tr],holdout_coefficients=[r['effective_Crr'] for r in ho],boundary='DC-link gross positive draw; not battery terminal net; no independent GMTLSV calibration')
    return summary,audit,[r for r,_ in records],sample

if __name__=='__main__':
    result,audit,trip,intervals=calculate(); print(json.dumps(result,indent=2));csvout(CAL/'file_audit.csv',audit);csvout(CAL/'trip_replay.csv',trip);csvout(CAL/'eligible_intervals.csv',intervals);(CAL/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
