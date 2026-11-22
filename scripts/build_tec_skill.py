"""Prospective, paired 365-day skill for SWIFT-TEC-linked foF2 sensitivity.

Records one small station-based forecast snapshot from an already issued
SWIFT-ION ion_forecast.json, then matches only PRIOR snapshots against newly
received GIRO/KC2G-derived ionosonde observations.

The fair comparison is SAME snapshot + station + valid UTC + observation:
IRI baseline and bounded TEC-linked scenario are scored on the identical
eligible population. Do not claim this is validated TEC assimilation, nor
backfill historical forecasts using hindsight.
"""
from __future__ import annotations
import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import json
import math
from pathlib import Path
from statistics import mean

from build_year_archive import (read_daily, write_daily, dates, valid_number,
                                FOF2_TOL_MHZ, RETENTION_DAYS)
from build_prospective_skill import iso, parse_utc, next_utc_hour, HORIZONS_H, save

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'swift-ion-tec-fof2-prospective-v1'
REPORT_SCHEMA = 'swift-ion-tec-fof2-skill-365-v1'
MAX_ISSUANCE_AGE_H = 3
MAX_STATIONS = 16
MAX_SPATIAL_JP_KM = 750
MAX_SPATIAL_GLOBAL_KM = 2500


def distance_km(a, b):
    la, lo, lb, lob = map(math.radians, (a[0], a[1], b[0], b[1]))
    x = math.sin(la)*math.sin(lb)+math.cos(la)*math.cos(lb)*math.cos(lo-lob)
    return 6371*math.acos(min(1, max(-1,x)))


def is_japan(lat, lon):
    return 23 <= lat <= 47 and 121 <= lon <= 152


def sample_station(frame, lat, lon):
    """Local IDW sampled from *published* model sites, no IRI recomputation.

    Missing TEC scenario remains missing. No interpolation from invalid far-off
    TEC cells, and no use of observations in prediction inputs.
    """
    nearby = []
    for cell in frame.get('sites', []):
        try:
            clat, clon = float(cell['lat']), float(cell['lon'])
            if not (-90 <= clat <= 90 and -180 <= clon <= 180):
                continue
            nearby.append((distance_km((lat,lon),(clat,clon)), cell))
        except (KeyError, ValueError, TypeError):
            continue
    nearby.sort(key=lambda x:x[0])
    nearby = nearby[:4]
    cap = MAX_SPATIAL_JP_KM if is_japan(lat,lon) else MAX_SPATIAL_GLOBAL_KM
    if not nearby or nearby[0][0] > cap:
        return None
    # For the hypothetical TEC linked scenario, do not renormalize a sparse
    # handful of separated accepted cells into a fabricated continuous field.
    rows = [(d,c) for d,c in nearby if d <= cap]
    if not rows:
        return None
    exact = rows[0][0] < .5
    if exact:
        rows = rows[:1]
    elif len(rows) < 2:
        return None
    weights = [1/max(50,d)**2 for d,_ in rows]

    def aggregate(key, require_all=False):
        data = [(w, c.get(key)) for w,(_,c) in zip(weights,rows)]
        if require_all and any(not valid_number(v) for w,v in data):
            return None
        good = [(w,v) for w,v in data if valid_number(v) and 0 <= v <= 40]
        return sum(w*v for w,v in good)/sum(w for w,v in good) if good else None

    baseline = aggregate('fof2_iri_mhz', require_all=True)
    linked = aggregate('fof2_tec_mhz', require_all=True)
    if baseline is None or not (0 < baseline <= 35):
        return None
    return {'predicted_fof2_iri_mhz':round(baseline,4),
            'predicted_fof2_tec_mhz':round(linked,4) if linked is not None and 0<linked<=35 else None,
            'nearest_model_site_km':round(rows[0][0],2),
            'model_sites_used':len(rows), 'sampling':'SPATIAL_IDW_OF_SAME_ISSUE_MODEL_SITES'}


def build_snapshot(model, observations, now, max_stations=MAX_STATIONS):
    if model.get('schema') != 'swift-ion-iri-tec-forecast-v1':
        return None, 'MODEL_SCHEMA_UNAVAILABLE'
    issued_model = parse_utc(model['metadata']['issued_at'])
    age=(now-issued_model).total_seconds()/3600
    if not (0 <= age <= MAX_ISSUANCE_AGE_H):
        return None, 'MODEL_ISSUE_STALE_OR_FUTURE'
    if not model.get('frames') or model.get('status') not in ('AVAILABLE','HISTORICAL_REPLAY_ONLY'):
        return None, 'MODEL_FORECAST_UNAVAILABLE'
    by_time = {parse_utc(f['valid_at']): f for f in model['frames']}
    forecasts=[]
    unique=set()
    for obs in observations.get('stations', []):
        if len(unique) >= max_stations: break
        try:
            name = str(obs['station']).strip()
            lat, lon = float(obs['lat']),float(obs['lon'])
            if not name or name in unique or not (-90<=lat<=90 and -180<=lon<=180): continue
        except (ValueError, TypeError, KeyError):
            continue
        unique.add(name)
        for h in HORIZONS_H:
            target = next_utc_hour(now+timedelta(hours=h))
            if target < now+timedelta(minutes=30): continue
            fr=by_time.get(target)
            if fr is None: continue
            sampled=sample_station(fr,lat,lon)
            if not sampled: continue
            forecasts.append({'station':name,'lat':round(lat,5),'lon':round(lon,5),
                  'valid_at':iso(target),'nominal_horizon_h':h,
                  'actual_lead_h':round((target-now).total_seconds()/3600,4),
                  **sampled})
    if not forecasts: return None, 'NO_VALID_STATION_FORECASTS'
    return {'metadata':{
        'schema':SCHEMA, 'issued_at':iso(now),'source_issued_at':iso(issued_model),
        'source_model_schema':model['schema'], 'source_is_validated':False,
        'model_type':'IRI-2020 future anchors plus bounded uniform SWIFT-TEC VTEC scaling',
        'experiment':'foF2 correction via square root of eligible TEC ratio',
        'is_3d_observation':False,'station_catalog':'KC2G/GIRO-derived public station metadata',
        'min_target_buffer_minutes':30, 'spatial_method':'local 4-neighbour IDW; complete TEC-only when all model cells eligible',
        'warning':'Prospective *experimental scenario*, not operational foF2 forecast or TEC assimilation.'},
        'forecasts':forecasts,'station_count':len(unique)}, 'AVAILABLE'


def recent_snapshots(history, now):
    start=(now-timedelta(hours=30)).date()
    result=[]
    for day in dates(start,now.date()):
        for s in read_daily(history/'tec_outlooks',day):
            try:
                t=parse_utc(s['metadata']['issued_at'])
                if s['metadata']['schema']==SCHEMA and now-timedelta(hours=30)<=t<now:
                    result.append(s)
            except (KeyError,TypeError,ValueError):pass
    return result


def score_observations(observations, snapshots, now):
    best={}
    for obs in observations.get('stations', []):
        try:
            obs_at = parse_utc(obs['observed_at'])
            if obs_at > now+timedelta(minutes=5): continue
            if obs.get('confidence_known') is not True or not valid_number(obs.get('confidence')) or obs['confidence']<70: continue
            name=str(obs['station'])
            observed=obs.get('fof2_mhz')
            if not valid_number(observed) or not (0<observed<=35):continue
        except (TypeError,ValueError,KeyError):continue
        for snapshot in snapshots:
            issued=parse_utc(snapshot['metadata']['issued_at'])
            if issued>=obs_at-timedelta(minutes=30):continue
            for f in snapshot['forecasts']:
                if f['station'] != name:continue
                target=parse_utc(f['valid_at'])
                if not (issued < target <= now):continue
                gap=abs((obs_at-target).total_seconds())/60
                if gap>30:continue
                if distance_km((float(obs['lat']),float(obs['lon'])),(f['lat'],f['lon']))>25:continue
                h=int(f['nominal_horizon_h'])
                if h not in HORIZONS_H: continue
                row={'station':name,'lat':float(obs['lat']),'lon':float(obs['lon']),
                     'issued_at':iso(issued),'valid_at':iso(target),'observed_at':iso(obs_at),
                     'nominal_horizon_h':h,'actual_lead_h':f.get('actual_lead_h'),
                     'time_gap_minutes':round((obs_at-target).total_seconds()/60,3),
                     'confidence':obs['confidence'],'observed_fof2_mhz':observed,
                     'predicted_fof2_iri_mhz':f.get('predicted_fof2_iri_mhz'),
                     'predicted_fof2_tec_mhz':f.get('predicted_fof2_tec_mhz'),
                     'nearest_model_site_km':f.get('nearest_model_site_km'),
                     'source_issued_at':snapshot['metadata']['source_issued_at']}
                key=(name,iso(target),h)
                prior=best.get(key)
                # Closest accepted observation, latest issue as tie-break.
                if prior is None or (gap,-issued.timestamp()) < (abs(prior['time_gap_minutes']),-parse_utc(prior['issued_at']).timestamp()):
                    best[key]=row
    return list(best.values())


def store_snapshot(history, snapshot):
    d=parse_utc(snapshot['metadata']['issued_at']).date()
    rows=read_daily(history/'tec_outlooks',d)
    by_id={r['metadata']['issued_at']:r for r in rows}
    by_id[snapshot['metadata']['issued_at']]=snapshot
    write_daily(history/'tec_outlooks',d,sorted(by_id.values(),key=lambda s:s['metadata']['issued_at']))


def store_matches(history, rows, now):
    by_day=defaultdict(list)
    cutoff=now.date()-timedelta(days=RETENTION_DAYS-1)
    for r in rows:
        day=parse_utc(r['valid_at']).date()
        if cutoff<=day<=now.date():by_day[day].append(r)
    count=0
    for day, new in by_day.items():
        previous=read_daily(history/'tec_matches',day)
        existing={(r['station'],r['valid_at'],r['nominal_horizon_h']):r for r in previous}
        for r in new:
            key=(r['station'],r['valid_at'],r['nominal_horizon_h'])
            old=existing.get(key)
            if old is None:count+=1
            if old is None or (abs(r['time_gap_minutes']),-parse_utc(r['issued_at']).timestamp()) < (abs(old['time_gap_minutes']),-parse_utc(old['issued_at']).timestamp()):
                existing[key]=r
        write_daily(history/'tec_matches',day,sorted(existing.values(),key=lambda r:(r['valid_at'],r['station'],r['nominal_horizon_h'])))
    return count


def metric(rows, key):
    differences=[r[key]-r['observed_fof2_mhz'] for r in rows if valid_number(r.get(key)) and valid_number(r.get('observed_fof2_mhz'))]
    n=len(differences)
    if not n:return {'sample_count':0,'hit_count':0,'hit_rate_percent':None,'mae':None,'rmse':None,'bias':None}
    return {'sample_count':n,'hit_count':sum(abs(d)<=FOF2_TOL_MHZ for d in differences),
            'hit_rate_percent':round(100*sum(abs(d)<=FOF2_TOL_MHZ for d in differences)/n,2),
            'mae':round(mean(abs(d) for d in differences),4),
            'rmse':round(math.sqrt(mean(d*d for d in differences)),4),
            'bias':round(mean(differences),4)}


def paired_summary(rows):
    all_baseline=metric(rows,'predicted_fof2_iri_mhz')
    accepted=[r for r in rows if valid_number(r.get('predicted_fof2_iri_mhz')) and valid_number(r.get('predicted_fof2_tec_mhz')) and valid_number(r.get('observed_fof2_mhz'))]
    iri=metric(accepted,'predicted_fof2_iri_mhz')
    tec=metric(accepted,'predicted_fof2_tec_mhz')
    improvement=round(tec['hit_rate_percent']-iri['hit_rate_percent'],2) if accepted else None
    return {'matching_records':len(rows),'iri_all':all_baseline,'paired_iri':iri,
            'paired_tec':tec,'paired_count':len(accepted),
            'tec_coverage_percent':round(100*len(accepted)/all_baseline['sample_count'],2) if all_baseline['sample_count'] else None,
            'hit_rate_gain_pp':improvement}


def report(history, now):
    start=now.date()-timedelta(days=RETENTION_DAYS-1)
    hrows=defaultdict(list); dayrows=defaultdict(list); monthrows=defaultdict(list)
    seen=set(); total=0
    for d in dates(start,now.date()):
        for row in read_daily(history/'tec_matches',d):
            try:
                h=int(row['nominal_horizon_h'])
                if h not in HORIZONS_H:continue
                hrows[h].append(row);dayrows[(d.isoformat(),h)].append(row)
                monthrows[(d.strftime('%Y-%m'),h)].append(row)
                seen.add(d.isoformat());total+=1
            except (ValueError,TypeError,KeyError):continue
    daily=[{'day_utc':d.isoformat(),'horizon_h':h,'summary':paired_summary(dayrows[(d.isoformat(),h)])}
           for d in dates(start,now.date()) for h in HORIZONS_H]
    months=sorted({d.strftime('%Y-%m') for d in dates(start,now.date())})
    monthly=[{'month_utc':m,'horizon_h':h,'summary':paired_summary(monthrows[(m,h)])}
             for m in months for h in HORIZONS_H]
    byh={str(h):paired_summary(hrows[h]) for h in HORIZONS_H}
    return {'schema':REPORT_SCHEMA,'metadata':{'generated_at':iso(now),
        'window_start_utc':start.isoformat(),'window_end_utc':now.date().isoformat(),
        'retention_days':365,'fof2_hit_threshold_mhz':FOF2_TOL_MHZ,
        'comparison':'Same prospectively issued model, station, valid UTC and observation; only paired eligible TEC scenarios',
        'source':'SWIFT-TEC 30-min VTEC + future IRI-2020 anchors; KC2G/GIRO-derived stations',
        'observations_license':'GIRO-derived via KC2G: CC BY-NC-SA 4.0; noncommercial; acknowledge station providers',
        'is_validated_assimilative_forecast':False,'is_hmf2_tec_skill':False,
        'is_3d_density_skill':False,
        'warning':'Research-only uniform scaling scenario. Ineligible TEC corrections excluded from paired denominator. Missing observations do not count as misses; no backfill of issued forecasts.'},
        'status':'AVAILABLE' if sum(x['paired_count'] for x in byh.values()) else 'AWAITING_PAIRED_PROSPECTIVE_MATCHES',
        'total_matches':total,'observation_days_with_matches':len(seen),
        'by_horizon':byh,'daily':daily,'monthly':monthly}


def export_csv(path, rows, date_key):
    names=[date_key,'horizon_h','matching_records','all_iri_n','paired_n','tec_coverage_pct',
           'iri_hit_pct_paired','tec_hit_pct_paired','gain_percentage_points',
           'iri_mae_mhz_paired','tec_mae_mhz_paired','iri_rmse_mhz_paired','tec_rmse_mhz_paired',
           'iri_bias_mhz_paired','tec_bias_mhz_paired']
    with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=names);w.writeheader()
        for item in rows:
            s=item['summary'];iri=s['paired_iri'];tec=s['paired_tec'];base={date_key:item[date_key],
            'horizon_h':item['horizon_h'],'matching_records':s['matching_records'],'all_iri_n':s['iri_all']['sample_count'],
            'paired_n':s['paired_count'],'tec_coverage_pct':s['tec_coverage_percent'],
            'iri_hit_pct_paired':iri['hit_rate_percent'],'tec_hit_pct_paired':tec['hit_rate_percent'],
            'gain_percentage_points':s['hit_rate_gain_pp']}
            for key in ('mae','rmse','bias'):
                base[f'iri_{key}_mhz_paired']=iri[key];base[f'tec_{key}_mhz_paired']=tec[key]
            w.writerow(base)


def prune(history,now):
    cutoff=now.date()-timedelta(days=RETENTION_DAYS-1)
    removed=0
    for kind in ('tec_outlooks','tec_matches'):
        folder=history/kind
        if not folder.exists():continue
        for fp in folder.glob('*.jsonl.gz'):
            try:
                from datetime import date
                day=date.fromisoformat(fp.name.removesuffix('.jsonl.gz'))
                if day<cutoff:fp.unlink();removed+=1
            except ValueError:continue
    return removed


def run(observations_file, model_file, history, docs, *, now=None, issue_new=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('now must be timezone-aware')
    observations=json.loads(Path(observations_file).read_text(encoding='utf-8'))
    history=Path(history);docs=Path(docs)
    history.mkdir(parents=True,exist_ok=True);docs.mkdir(parents=True,exist_ok=True)
    previous=recent_snapshots(history,now)
    matches=score_observations(observations,previous,now)
    count=store_matches(history,matches,now)
    if issue_new is None:
        issue_new=not previous or now- max(parse_utc(s['metadata']['issued_at']) for s in previous)>=timedelta(hours=6)
    reason='NOT_SCHEDULED'
    snapshot=None
    if issue_new:
        try:
            model=json.loads(Path(model_file).read_text(encoding='utf-8'))
            snapshot,reason=build_snapshot(model,observations,now)
            if snapshot:store_snapshot(history,snapshot)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            reason='SOURCE_UNAVAILABLE: '+str(exc)[:150]
    removed=prune(history,now)
    payload=report(history,now)
    payload['archive']={'new_snapshot_issued':snapshot is not None,
        'snapshot_status':reason, 'previous_snapshots_30h':len(previous),
        'new_matches':count,'expired_file_count':removed,
        'snapshot_days':len(list((history/'tec_outlooks').glob('*.jsonl.gz'))),
        'match_days':len(list((history/'tec_matches').glob('*.jsonl.gz')))}
    save(docs/'tec_skill.json',payload)
    export_csv(docs/'tec_skill_daily.csv',payload['daily'],'day_utc')
    export_csv(docs/'tec_skill_monthly.csv',payload['monthly'],'month_utc')
    print('TEC paired 365-day skill:',payload['status'],'matched',payload['total_matches'],
          'new',count,'issued',snapshot is not None,'reason',reason,flush=True)
    return payload


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--observations',type=Path,default=ROOT/'docs/ionosonde_validation.json')
    parser.add_argument('--model',type=Path,default=ROOT/'docs/ion_forecast.json')
    parser.add_argument('--history',type=Path,default=ROOT/'_swift_ion_history')
    parser.add_argument('--docs',type=Path,default=ROOT/'docs')
    a=parser.parse_args()
    run(a.observations,a.model,a.history,a.docs)


if __name__=='__main__':main()
