"""Fit only historical PROSPECTIVELY issued foF2 pairs as of this run.
Chronological (not random) train / validation selection; no future labels.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone,timedelta
import json
import math
from pathlib import Path
from statistics import mean
from fof2_ml import SCHEMA, EMP_NAMES, AI_NAMES, num, time_utc, feature_vector, solve_ridge, predict_correction
from build_year_archive import read_daily,dates,RETENTION_DAYS

ROOT=Path(__file__).resolve().parents[1]


def training_rows(history,now):
    cutoff=now-timedelta(hours=1)
    first=now.date()-timedelta(days=RETENTION_DAYS-1)
    best={}
    for day in dates(first,now.date()):
        # GIRO/KC2G + independent NICT observations (if ingested), with
        # identical issue-before-observation leakage safeguards. Missing NICT
        # data never synthesizes examples; it simply contributes zero rows.
        historic=read_daily(Path(history)/'tec_matches',day)
        historic+=read_daily(Path(history)/'nict_matches',day)
        for m in historic:
            try:
                # Provisional extended estimates are evaluated separately,
                # never used to fit coefficients trained for STANDARD inputs.
                if m.get('fof2_quality','STANDARD') != 'STANDARD':continue
                issue=time_utc(m['issued_at']);obs=time_utc(m['observed_at']);valid=time_utc(m['valid_at'])
                if not (issue<valid and issue<obs-timedelta(minutes=30) and obs<cutoff):continue
                real=num(m.get('observed_fof2_mhz'),0.1,35)
                physical=num(m.get('predicted_fof2_physics_mhz'),0.1,35)
                # Prior schema was only physics scaling; use it when genuinely archival.
                if physical is None and 'predicted_fof2_physics_mhz' not in m:
                    physical=num(m.get('predicted_fof2_tec_mhz'),0.1,35)
                reference=num(m.get('predicted_fof2_iri_mhz'),0.1,35)
                if real is None or physical is None or reference is None:continue
                lat=float(m['lat']);lon=float(m['lon'])
                kp=num(m.get('kp_forecast'),0,9);f107=num(m.get('f107_available'),50,400)
                # No source date or non-issue Kp feature means neutral, never future observation.
                x=feature_vector(physical,reference,lat,lon,valid,kp,f107)
                if x is None:continue
                row={'issued_at':issue,'observed_at':obs,'day':obs.date().isoformat(),
                     'station':str(m['station']),'lat':lat,'lon':lon,'valid_at':valid,
                     'physical':physical,'reference':reference,'actual':real,'kp':kp,'f107':f107}
                # Do not double-count the same station/time across GIRO and NICT
                # aliases; prefer NICT when both have measurements.
                key=(round(lat,1),round(lon,1),obs.isoformat())
                row['data_provider']='NICT' if 'observation_source' in m else 'GIRO_KC2G'
                old=best.get(key)
                if old is None or (row['data_provider']=='NICT' and old['data_provider']!='NICT') or (row['data_provider']==old['data_provider'] and issue<old['issued_at']):
                    best[key]=row
            except (KeyError,TypeError,ValueError,OverflowError):continue
    return sorted(best.values(),key=lambda r:r['observed_at'])


def mae(rows,preds):return mean(abs(r['actual']-p) for r,p in zip(rows,preds)) if rows else None


def fit_empirical(rows):
    X=[feature_vector(r['physical'],r['reference'],r['lat'],r['lon'],r['valid_at'],r['kp'],r['f107']) for r in rows]
    y=[r['actual']-r['physical'] for r in rows]
    return solve_ridge(X,y,reg=12.0)


def empirical_preds(rows,co):
    return [min(35,max(.1,r['physical']+predict_correction(co,feature_vector(r['physical'],r['reference'],r['lat'],r['lon'],r['valid_at'],r['kp'],r['f107']),1.5))) for r in rows]


def fit_ai(rows,emp):
    X=[feature_vector(r['physical'],r['reference'],r['lat'],r['lon'],r['valid_at'],r['kp'],r['f107'],kind='ai') for r in rows]
    p=empirical_preds(rows,emp)
    return solve_ridge(X,[r['actual']-v for r,v in zip(rows,p)],reg=30.0)


def ai_preds(rows, emp, ai):
    base=empirical_preds(rows,emp)
    return [min(35,max(.1,v+predict_correction(ai,feature_vector(r['physical'],r['reference'],r['lat'],r['lon'],r['valid_at'],r['kp'],r['f107'],kind='ai'),1.25))) for r,v in zip(rows,base)]


def fit(history,now):
    rows=training_rows(history,now)
    dates_available=sorted({r['day'] for r in rows})
    output={'schema':SCHEMA,'trained_at':now.isoformat().replace('+00:00','Z'),
      'training_rows':len(rows),'independent_observation_days':len(dates_available),
      'nict_training_rows':sum(r.get('data_provider')=='NICT' for r in rows),
      'giro_training_rows':sum(r.get('data_provider')!='NICT' for r in rows),
      'source':'Prospectively issued foF2 + later GIRO/KC2G and optionally NICT four-site observations (source tagged)',
      'future_observations_used':False,'method':'Chronological split, ridge empirical + nonlinear ridge ML residual',
      'empirical':{'active':False,'coefficients':None,'feature_names':EMP_NAMES,'holdout_mae_physics_mhz':None,'holdout_mae_empirical_mhz':None},
      'ai':{'active':False,'coefficients':None,'feature_names':AI_NAMES,'holdout_mae_empirical_mhz':None,'holdout_mae_ai_mhz':None},
      'status':'PHYSICS_ONLY',
      'notes':['No correction is deployed until independent future-in-time holdout improves MAE.',
               'NOAA forecast Kp and latest already-observed F10.7 may be used only if available at issuance; unavailable features are neutral.',
               'AI here is a compact nonlinear ridge regression, not deep learning.',
               'Do not infer ionospheric vertical structure from calibrated foF2 alone.']}
    if len(rows)<48 or len(dates_available)<14:return output
    nvalid=max(4,math.ceil(.2*len(dates_available)))
    holdout=set(dates_available[-nvalid:]);train=[r for r in rows if r['day'] not in holdout];test=[r for r in rows if r['day'] in holdout]
    if len(train)<32 or len(test)<8:return output
    emp=fit_empirical(train)
    pb=mae(test,[r['physical'] for r in test]);pe=mae(test,empirical_preds(test,emp))
    output['empirical'].update(holdout_mae_physics_mhz=round(pb,4),holdout_mae_empirical_mhz=round(pe,4),
                               holdout_days=nvalid,training_samples=len(train),validation_samples=len(test))
    if not (pe<=pb-.02):return output
    output['empirical'].update(active=True,coefficients=[round(c,8) for c in fit_empirical(rows)])
    output['status']='EMPIRICAL_ACTIVE'
    if len(rows)<160 or len(dates_available)<35 or len(train)<120 or len(test)<24:return output
    ai=fit_ai(train,emp)
    pa=mae(test,ai_preds(test,emp,ai))
    output['ai'].update(holdout_mae_empirical_mhz=round(pe,4),holdout_mae_ai_mhz=round(pa,4),
                        holdout_days=nvalid,training_samples=len(train),validation_samples=len(test))
    if pa<=pe-.03:
        emp_full=output['empirical']['coefficients']
        output['ai'].update(active=True,coefficients=[round(c,8) for c in fit_ai(rows,emp_full)])
        output['status']='AI_ACTIVE'
    return output


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--history',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    now=datetime.now(timezone.utc);model=fit(args.history,now)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(model,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8')
    print('foF2 training:',model['status'],model['training_rows'],'independent samples',model['independent_observation_days'],'days',flush=True)

if __name__=='__main__':main()
