"""SWIFT-ION foF2 research calibration. Stdlib-only, issue-time-safe regression.

Pipeline:
 (1) physics: foF2 [MHz] = 8.98e-6 * sqrt(NmF2 [m-3]), with equivalent-slab
     assumption for VTEC/partial-TEC ratio already gated by build_ion_forecast.
 (2) empirical: ridge-regularized polynomial correction based on physical
     TEC ratio, local time, season, and *issued-time available* Kp/F10.7.
 (3) AI: nonlinear feature expansion + regularized machine learning residual.
     The nonlinear ML stage is activated only on chronological holdout gain.

This is not deep learning, self-consistent 3D tomography, or validated operational
prediction. No unseen observations may inform a current issuance.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math

SCHEMA = 'swift-ion-fof2-calibration-v1'
EMP_NAMES = ['intercept','r','r2','r3','local_sin','local_cos','annual_sin','annual_cos','kp_delta','f107_delta']
AI_NAMES = ['intercept','r','r2','r3','local_sin','local_cos','annual_sin','annual_cos','kp_delta','f107_delta',
            'latitude','r_local_sin','r_local_cos','r_annual_sin','r_annual_cos','r_latitude',
            'kp_r','f107_r','kp_sq','f107_sq','diurnal_harmonic','annual_harmonic']


def num(x, lo=-1e12, hi=1e12):
    if isinstance(x,bool): return None
    try: n=float(x)
    except (TypeError, ValueError):return None
    return n if math.isfinite(n) and lo<=n<=hi else None


def time_utc(value):
    if isinstance(value,datetime):d=value
    else:d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('UTC offset required')
    return d.astimezone(timezone.utc)


def feature_vector(fof2_physics, fof2_iri, lat, lon, valid_at, kp=None, f107=None, kind='empirical'):
    base=num(fof2_physics,0.01,35);ref=num(fof2_iri,0.01,35)
    latitude=num(lat,-90,90);longitude=num(lon,-180,180)
    if base is None or ref is None or latitude is None or longitude is None:
        return None
    dt=time_utc(valid_at)
    ratio=max(0.5,min(2.0,(base/ref)**2))
    r=ratio-1.0
    solar=(dt.hour+dt.minute/60.0+longitude/15.0)%24
    a=2*math.pi*solar/24
    b=2*math.pi*((dt.timetuple().tm_yday-1)+(dt.hour/24))/365.25
    k=num(kp,0,9);f=num(f107,50,400)
    # Missing driver means a neutral feature, NOT a fabricated geomagnetic value.
    kd=0.0 if k is None else (k-3.0)/4.0
    fd=0.0 if f is None else (f-130.0)/130.0
    s,c,ss,cc=math.sin(a),math.cos(a),math.sin(b),math.cos(b)
    core=[1.,r,r*r,r*r*r,s,c,ss,cc,kd,fd]
    if kind=='empirical':return core
    if kind!='ai':raise ValueError('Unknown stage')
    lati=latitude/90
    return core + [lati,r*s,r*c,r*ss,r*cc,r*lati,kd*r,fd*r,kd*kd,fd*fd,math.sin(2*a),math.sin(2*b)]


def solve_ridge(vectors, targets, reg=8.0):
    if not vectors or len(vectors)!=len(targets):raise ValueError('Bad ridge training data')
    n=len(vectors[0]);matrix=[[0.0]*(n+1) for _ in range(n)]
    for v,y in zip(vectors,targets):
        if len(v)!=n:raise ValueError('Feature mismatch')
        for i in range(n):
            matrix[i][n]+=v[i]*y
            for j in range(n):matrix[i][j]+=v[i]*v[j]
    for i in range(n):matrix[i][i]+=reg*(.15 if i==0 else 1)
    for i in range(n):
        j=max(range(i,n),key=lambda k:abs(matrix[k][i]))
        matrix[i],matrix[j]=matrix[j],matrix[i]
        d=matrix[i][i]
        if abs(d)<1e-9:raise ValueError('Singular training matrix')
        for k in range(i,n+1):matrix[i][k]/=d
        for row in range(n):
            if row==i:continue
            v=matrix[row][i]
            for col in range(i,n+1):matrix[row][col]-=v*matrix[i][col]
    return [matrix[i][n] for i in range(n)]


def predict_correction(coeffs, features, limit=2.0):
    if not coeffs or not features or len(coeffs)!=len(features):return 0.0
    value=sum(a*b for a,b in zip(coeffs,features))
    return max(-limit,min(limit,value)) if math.isfinite(value) else 0.0


def stage_predict(base, ref, lat, lon, valid_at, kp, f107, model):
    """Returns stage predictions with AI/empirical None until verified ready.

    The final operational *research* forecast falls back to the latest active
    stage; absent predictions are never numerically fabricated.
    """
    physical=num(base,0.01,35)
    if physical is None:return {'physics':None,'empirical':None,'ai':None,'selected':None,'stage':'UNAVAILABLE'}
    physical=round(physical,4)
    out={'physics':physical,'empirical':None,'ai':None,'selected':physical,'stage':'PHYSICS'}
    if not model or model.get('schema')!=SCHEMA:return out
    try:
        asof=time_utc(model['trained_at']);valid=time_utc(valid_at)
        if asof>=valid:return out
    except (ValueError,KeyError,TypeError):return out
    x=feature_vector(physical,ref,lat,lon,valid_at,kp,f107)
    if x is None:return out
    co=model.get('empirical',{}).get('coefficients')
    if model.get('empirical',{}).get('active') and isinstance(co,list) and len(co)==len(EMP_NAMES):
        empirical=max(0.1,min(35.0,physical+predict_correction(co,x,1.5)))
        out.update(empirical=round(empirical,4),selected=round(empirical,4),stage='EMPIRICAL')
        features=feature_vector(physical,ref,lat,lon,valid_at,kp,f107,kind='ai')
        ai_co=model.get('ai',{}).get('coefficients')
        if model.get('ai',{}).get('active') and isinstance(ai_co,list) and len(ai_co)==len(AI_NAMES):
            value=max(0.1,min(35.0,empirical+predict_correction(ai_co,features,1.25)))
            out.update(ai=round(value,4),selected=round(value,4),stage='AI')
    return out
