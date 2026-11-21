"""SWIFT-ION v1.1: 365-day, Git-backed prospective IRI baseline verification.

The archive is stored on an independent Git branch, not in Actions artifacts.
This module must be executed after the KC2G station check and before the branch
is committed/pushed. It never calls a live model for the *past* to claim skill.

Public GIRO-derived records are CC BY-NC-SA 4.0; noncommercial research only;
acknowledge the original ionosonde operators. NOT a SWIFT-TEC layer forecast.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import csv
import gzip
import io
import json
import math
import os
from pathlib import Path
from statistics import mean

from build_prospective_skill import (
    build_outlook, iso, parse_utc, score_history, save, HORIZONS_H,
)

ROOT = Path(__file__).resolve().parents[1]
RETENTION_DAYS = 365
FOF2_TOL_MHZ = 1.0
HMF2_TOL_KM = 30.0
METRIC_FIELDS = {
    'fof2': ('predicted_fof2_mhz', 'observed_fof2_mhz', FOF2_TOL_MHZ, 'MHz'),
    'hmf2': ('predicted_hmf2_km', 'observed_hmf2_km', HMF2_TOL_KM, 'km'),
}
LICENSE = 'GIRO/INGV-derived via KC2G; CC BY-NC-SA 4.0; noncommercial; acknowledge each station provider'


def valid_number(n):
    return isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n)


def read_daily(directory: Path, day: date):
    path = directory / (day.isoformat() + '.jsonl.gz')
    if not path.exists():
        return []
    if path.stat().st_size > 5_000_000:
        raise ValueError(f'History daily chunk too large: {path.name}')
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def write_daily(directory: Path, day: date, records):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (day.isoformat() + '.jsonl.gz')
    raw = ''.join(json.dumps(r, ensure_ascii=False, allow_nan=False,
                              separators=(',', ':'), sort_keys=True) + '\n' for r in records).encode('utf-8')
    tmp = path.with_suffix('.tmp')
    tmp.write_bytes(gzip.compress(raw, compresslevel=6, mtime=0))
    tmp.replace(path)


def dates(start: date, end: date):
    for n in range((end-start).days+1):
        yield start + timedelta(days=n)


def recent_outlooks(history: Path, now: datetime):
    # 24h nominal lead plus UTC-hour rounding and publication buffering.
    start = (now - timedelta(hours=30)).date()
    snapshots = []
    for day in dates(start, now.date()):
        for s in read_daily(history / 'outlooks', day):
            try:
                issued = parse_utc(s['metadata']['issued_at'])
                if now - timedelta(hours=30) <= issued < now:
                    snapshots.append(s)
            except (ValueError, KeyError, TypeError):
                continue
    return snapshots


def minimal_obs(item):
    try:
        t = parse_utc(item['observed_at'])
        name = str(item['station']).strip()
        lat, lon = float(item['lat']), float(item['lon'])
        if not name or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        d = {'station': name, 'lat': lat, 'lon': lon, 'observed_at': iso(t),
             'fof2_mhz': item.get('fof2_mhz'), 'hmf2_km': item.get('hmf2_km'),
             'confidence': item.get('confidence'), 'confidence_known': item.get('confidence_known')}
        if not any(valid_number(d[k]) for k in ('fof2_mhz','hmf2_km')):
            return None
        return d
    except (KeyError, TypeError, ValueError):
        return None


def update_observations(history: Path, observations, now: datetime):
    added = 0
    window_start = now.date() - timedelta(days=RETENTION_DAYS-1)
    by_day = defaultdict(list)
    for station in observations.get('stations', []):
        obs = minimal_obs(station)
        if not obs:
            continue
        d = parse_utc(obs['observed_at']).date()
        if window_start <= d <= now.date():
            by_day[d].append(obs)
    for day, new in by_day.items():
        current = {(x['station'],x['observed_at']):x for x in read_daily(history/'observations',day)}
        for x in new:
            key = (x['station'], x['observed_at'])
            if key not in current:
                added += 1
            current[key] = x
        write_daily(history/'observations',day,sorted(current.values(),key=lambda x:(x['observed_at'],x['station'])))
    return added


def update_matches(history: Path, matches, now: datetime):
    added = 0
    window_start = now.date() - timedelta(days=RETENTION_DAYS-1)
    by_day = defaultdict(list)
    for m in matches:
        try:
            day = parse_utc(m['valid_at']).date()
            if not (window_start <= day <= now.date()):
                continue
            issue_at=parse_utc(m['issued_at'])
            observed_at=parse_utc(m['observed_at'])
            valid_at=parse_utc(m['valid_at'])
            if (issue_at >= observed_at-timedelta(minutes=30)
                or valid_at <= issue_at
                or valid_at > now
                or observed_at > now+timedelta(minutes=5)
                or abs((observed_at-valid_at).total_seconds()) > 1800):
                continue
            if int(m['nominal_horizon_h']) not in HORIZONS_H:
                continue
            if not valid_number(m.get('confidence')) or m['confidence'] < 70:
                continue
            by_day[day].append(m)
        except (KeyError,TypeError,ValueError):
            continue
    for day, new in by_day.items():
        existing = {(x['station'],x['valid_at'],int(x['nominal_horizon_h'])):x
                    for x in read_daily(history/'matches',day)}
        for x in new:
            key=(x['station'],x['valid_at'],int(x['nominal_horizon_h']))
            old=existing.get(key)
            if old is None:
                added += 1
            if old is None or (abs(x['time_gap_minutes']), -parse_utc(x['issued_at']).timestamp()) < (abs(old['time_gap_minutes']), -parse_utc(old['issued_at']).timestamp()):
                existing[key]=x
        write_daily(history/'matches',day, sorted(existing.values(),key=lambda x:(x['valid_at'],x['station'],x['nominal_horizon_h'])))
    return added


def store_outlook(history: Path, outlook):
    if outlook.get('metadata',{}).get('schema') != 'swift-ion-prospective-iri-baseline-v1':
        raise ValueError('Unrecognized outlook schema')
    issued = parse_utc(outlook['metadata']['issued_at'])
    day = issued.date()
    old = read_daily(history/'outlooks',day)
    # Idempotent for a retried run with the same issued_at; no fabricated backfill.
    by_id = {o['metadata']['issued_at']:o for o in old}
    by_id[outlook['metadata']['issued_at']] = outlook
    write_daily(history/'outlooks',day,sorted(by_id.values(),key=lambda x:x['metadata']['issued_at']))


def prune(history: Path, today: date):
    cutoff = today - timedelta(days=RETENTION_DAYS-1)
    removed = 0
    for kind in ('outlooks','observations','matches'):
        folder=history/kind
        if not folder.exists():
            continue
        for path in folder.glob('*.jsonl.gz'):
            try:
                d = date.fromisoformat(path.name[:-9]) # strip .jsonl.gz
            except ValueError:
                continue
            if d < cutoff:
                path.unlink()
                removed+=1
    return removed


def all_matches(history: Path, now: datetime):
    start = now.date() - timedelta(days=RETENTION_DAYS-1)
    rows = []
    for day in dates(start,now.date()):
        rows.extend(read_daily(history/'matches',day))
    return rows


def metric_summary(rows, metric):
    pred, obs, tol, unit = METRIC_FIELDS[metric]
    diffs = [float(r[pred])-float(r[obs]) for r in rows
             if valid_number(r.get(pred)) and valid_number(r.get(obs))]
    n = len(diffs)
    if n == 0:
        return {'sample_count':0,'hit_count':0,'hit_rate_percent':None,'mae':None,
                'rmse':None,'bias':None,'threshold':tol,'unit':unit,'status':'NO_MATCHES'}
    hit = sum(abs(d) <= tol for d in diffs)
    return {'sample_count':n,'hit_count':hit,'hit_rate_percent':round(100*hit/n,2),
            'mae':round(mean(abs(d) for d in diffs),3),
            'rmse':round(math.sqrt(mean(d*d for d in diffs)),3),
            'bias':round(mean(diffs),3),'threshold':tol,'unit':unit,
            'status':'PROVISIONAL_SMALL_SAMPLE' if n < 10 else 'AVAILABLE'}


def aggregate(rows):
    return {'matching_records':len(rows), 'fof2':metric_summary(rows,'fof2'),
            'hmf2':metric_summary(rows,'hmf2')}


def write_csv(path: Path, rows, group_field):
    path.parent.mkdir(parents=True,exist_ok=True)
    cols=[group_field,'horizon_h','matching_records','fof2_count','fof2_hit_rate_pct',
          'fof2_mae_mhz','fof2_rmse_mhz','fof2_bias_mhz','hmf2_count','hmf2_hit_rate_pct',
          'hmf2_mae_km','hmf2_rmse_km','hmf2_bias_km']
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=cols)
        w.writeheader()
        for x in rows:
            a=x['summary'];o={'horizon_h':x['horizon_h'],group_field:x[group_field],
                              'matching_records':a['matching_records']}
            for key in ('fof2','hmf2'):
                metric=a[key]
                for name,source in [('count','sample_count'),('hit_rate_pct','hit_rate_percent'),
                                    ('mae_mhz' if key=='fof2' else 'mae_km','mae'),
                                    ('rmse_mhz' if key=='fof2' else 'rmse_km','rmse'),
                                    ('bias_mhz' if key=='fof2' else 'bias_km','bias')]:
                    o[key+'_'+name]=metric[source]
            w.writerow(o)


def report_year(history: Path, now: datetime):
    """Summarize only observed/verified matches; missing days remain N/A.

    Pre-bucket matches so a year of data does not cause O(days * matches)
    work on every scheduled update.
    """
    rows=all_matches(history,now)
    per_h=defaultdict(list)
    per_day_h=defaultdict(list)
    per_month_h=defaultdict(list)
    days_with_matches=set()
    for r in rows:
        try:
            h=int(r['nominal_horizon_h'])
            if h not in HORIZONS_H:
                continue
            date_utc=parse_utc(r['valid_at']).date()
        except (ValueError,KeyError,TypeError):
            continue
        per_h[h].append(r)
        per_day_h[(date_utc,h)].append(r)
        per_month_h[(date_utc.strftime('%Y-%m'),h)].append(r)
        days_with_matches.add(date_utc)
    by_h={str(h):aggregate(per_h[h]) for h in HORIZONS_H}
    start=now.date()-timedelta(days=RETENTION_DAYS-1)
    days=[{'day_utc':d.isoformat(),'horizon_h':h,'summary':aggregate(per_day_h[(d,h)])}
          for d in dates(start,now.date()) for h in HORIZONS_H]
    month_names=sorted({d.strftime('%Y-%m') for d in dates(start,now.date())})
    months=[{'month_utc':m,'horizon_h':h,'summary':aggregate(per_month_h[(m,h)])}
            for m in month_names for h in HORIZONS_H]
    return {'metadata':{'schema':'swift-ion-rolling-year-v1','generated_at':iso(now),
              'window_start_utc':start.isoformat(),'window_end_utc':now.date().isoformat(),
              'retention_days':RETENTION_DAYS,
              'forecast':'Prospectively issued IRI-2020 CLIMATOLOGY only',
              'is_swifttec_layer_forecast_skill':False,
              'source_license':LICENSE,
              'hit_definitions':{'fof2':'abs(IRI−observation) <= 1.0 MHz',
                                 'hmf2':'abs(IRI−observation) <= 30 km'},
              'deduplication':'one match per station, target valid UTC and nominal lead; closest accepted observation; latest eligible issuance breaks ties',
              'warnings':['Yearly window starts accumulating from first successful deployment; no historical forecasts are invented.',
                          'Unmatched, missing, or unverified observations are not counted as misses.',
                          'Multiple horizons can score one observation; pooled horizons are not independent.',
                          'IRI is a baseline climatology, not a TEC-corrected electron-density forecast.',
                          'IRI hmF2 is a sampled height-grid maximum (25 km step).',
                          'Retention is rolling 365 days in active branch files; prior git commits may contain older snapshots.']},
            'status':'AVAILABLE' if any(by_h[str(h)]['fof2']['sample_count'] or by_h[str(h)]['hmf2']['sample_count'] for h in HORIZONS_H) else 'AWAITING_PROSPECTIVE_MATCHES',
            'unique_observation_days_with_matches':len(days_with_matches),
            'total_matches':len(rows),
            'by_horizon':by_h,'daily':days,'monthly':months}


def run(obs_file: Path, history: Path, docs: Path, *, now=None, iri_function=None, issue_new=None, published_at=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Run UTC must be timezone-aware')
    observations=json.loads(Path(obs_file).read_text(encoding='utf-8'))
    if not isinstance(observations.get('stations'),list):
        raise ValueError('No station observations list in KC2G validation')
    history.mkdir(parents=True,exist_ok=True)
    snapshots=recent_outlooks(history,now)
    if issue_new is None:
        event=os.getenv('GITHUB_EVENT_NAME','')
        issue_new = event != 'schedule' or (now.hour % 6 == 0 and now.minute < 30)
    # Strict ordering: match only previously archived snapshots, then issue new one.
    latest=score_history(observations,snapshots,now)
    obs_added=update_observations(history,observations,now)
    matched_added=update_matches(history,latest['matches'],now)
    # Issue fresh IRI baseline at most once every six hours in scheduled runs.
    # Otherwise preserve and publish the most recent prior outlook without
    # manufacturing a new issue timestamp. A fresh git commit is not a model issue.
    if issue_new:
        if iri_function is None:
            from iri2020 import IRI as iri_function
        outlook=build_outlook(observations,iri_function,now,max_stations=12,published_at=published_at)
        if outlook['forecasts']:
            store_outlook(history,outlook)
    else:
        outlook=max(snapshots,key=lambda x:x['metadata']['issued_at']) if snapshots else {
            'metadata':{'schema':'swift-ion-prospective-iri-baseline-v1','issued_at':None},
            'status':'AWAITING_NEXT_ISSUE','forecasts':[],'station_count':0}
    save(docs/'station_outlook.json',outlook)
    removed=prune(history,now.date())
    yearly=report_year(history,now)
    yearly['archive']={'new_outlook_issued':bool(issue_new and outlook.get('forecasts')),
                       'stored_outlook_dates':len(list((history/'outlooks').glob('*.jsonl.gz'))),
                       'stored_observation_dates':len(list((history/'observations').glob('*.jsonl.gz'))),
                       'stored_match_dates':len(list((history/'matches').glob('*.jsonl.gz'))),
                       'new_observation_records':obs_added,'new_matches':matched_added,
                       'expired_daily_files':removed,'prior_snapshot_count':len(snapshots)}
    latest['history_status']='ROLLING_365_DAY_GIT_BRANCH'
    latest['annual_summary']={'total_matches':yearly['total_matches'],
                              'retention_days':365,'archive_branch':'swift-ion-history'}
    save(docs/'prospective_skill.json',latest)
    save(docs/'year_accuracy.json',yearly)
    write_csv(docs/'year_daily.csv',yearly['daily'],'day_utc')
    write_csv(docs/'year_monthly.csv',yearly['monthly'],'month_utc')
    (history/'README.md').write_text('# SWIFT-ION 365-day Research Archive\n\n'
        'Public station-derived data, noncommercial research only; GIRO / INGV / KC2G. '
        'CC BY-NC-SA 4.0, acknowledge individual ionosonde station providers.\n'
        'Contains prospective IRI **climatology** predictions, accepted public observations and matched errors. '
        'Not validated SWIFT-TEC layer forecasts. Daily compressed JSON Lines files.\n',encoding='utf-8')
    print('365-day archive:',len(snapshots),'prior issues,',matched_added,'new matches,',
          yearly['total_matches'],'retained matches;',outlook.get('status','ARCHIVED'),
          'new issuance' if issue_new else 'no new issuance',flush=True)
    return outlook,latest,yearly


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--observations',type=Path,default=ROOT/'docs/ionosonde_validation.json')
    p.add_argument('--history',type=Path,default=ROOT/'_swift_ion_history')
    p.add_argument('--docs',type=Path,default=ROOT/'docs')
    a=p.parse_args()
    run(a.observations,a.history,a.docs)
