"""NICT four-station foF2 bridge; fail-closed on unverified NICT file schemas.

Sources: normalized CSV downloaded from NICT archive / user-supplied source,
with explicit UTC timestamps or explicit JST columns. Direct URL mode is only
activated when operator supplies an already VERIFIED HTTPS download endpoint.
Unknown NICT native text formats are NOT guessed. No fabricated observation.

Only archives PREVIOUSLY issued TEC model snapshots; never calculates hindcasts.
Observations are used for next-issue training only and evaluation of published
snapshots. Attribution and permitted reuse must be verified by operator.
"""
from __future__ import annotations
import argparse, csv, io, json, math, os, ssl, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from build_year_archive import read_daily, write_daily, dates, RETENTION_DAYS
from build_prospective_skill import parse_utc, iso
from build_tec_skill import HORIZONS_H
from build_tec_skill import distance_km

ROOT=Path(__file__).resolve().parents[1]
STATIONS={
 'WAKKANAI':(45.16,141.75), 'KOKUBUNJI':(35.71,139.49),
 'YAMAGAWA':(31.20,130.62), 'OKINAWA':(26.68,128.15),
}
ALIASES={'SAROBETSU':'WAKKANAI','WK546':'WAKKANAI','WK':'WAKKANAI',
         'TO536':'KOKUBUNJI','TO535':'KOKUBUNJI','TO':'KOKUBUNJI',
         'YG431':'YAMAGAWA','YG':'YAMAGAWA','OK426':'OKINAWA','OK':'OKINAWA',
         'OGIMI':'OKINAWA','稚内':'WAKKANAI','国分寺':'KOKUBUNJI',
         '山川':'YAMAGAWA','沖縄':'OKINAWA','大宜味':'OKINAWA'}
FIELDS=('predicted_fof2_iri_mhz','predicted_fof2_tec_mhz',
        'predicted_fof2_physics_mhz','predicted_fof2_empirical_mhz','predicted_fof2_ai_mhz')
EXPORT='station,time_utc,fof2_mhz,source\n'


def canonical(raw):
    s=str(raw or '').strip().upper().replace('/','').replace(' ','')
    s=ALIASES.get(s,s)
    if s not in STATIONS:raise ValueError('Unknown station: '+s)
    return s


def parse_timestamp(row):
    utc_column=(row.get('time_utc') or '').strip()
    jst_column=(row.get('time_jst') or row.get('datetime_jst') or '').strip()
    if bool(utc_column)==bool(jst_column):raise ValueError('Specify exactly one time_utc or time_jst')
    if utc_column:
        if not utc_column.endswith('Z') and not (len(utc_column)>=6 and utc_column[-6] in '+-' and utc_column[-3]==':'):
            raise ValueError('time_utc must include Z or timezone offset')
        return parse_utc(utc_column)
    if jst_column.endswith('Z') or '+' in jst_column[-6:] or '-' in jst_column[-6:]:
        raise ValueError('time_jst must be timezone-free wall-clock JST')
    parsed=datetime.fromisoformat(jst_column.replace(' ','T'))
    if parsed.tzinfo is not None:raise ValueError('time_jst must not include timezone')
    return parsed.replace(tzinfo=timezone(timedelta(hours=9))).astimezone(timezone.utc)


def parse_normalized_csv(text, *, filename=None, source_url=None, now=None):
    now=now or datetime.now(timezone.utc)
    if len(text)>8_000_000:raise ValueError('CSV too large')
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    names=set(reader.fieldnames or [])
    if not {'fof2_mhz'}<=names or not ({'time_utc','time_jst','datetime_jst'} & names):
        raise ValueError('Unknown source format: normalize to station,time_utc,fof2_mhz,source or station,time_jst,fof2_mhz,source')
    if 'station' not in names and not filename:raise ValueError('Station column or station filename required')
    out=[];errors=0
    for i,r in enumerate(reader,2):
        try:
            st=canonical(r.get('station') or filename)
            t=parse_timestamp(r)
            val=str(r.get('fof2_mhz','')).strip()
            if not val or val in ('--','NaN','NULL','N/A','-999','999'):continue
            v=float(val)
            if not math.isfinite(v) or not (0.5<=v<=25):continue
            if not now-timedelta(days=RETENTION_DAYS+10)<=t<=now+timedelta(minutes=5):continue
            source=str(r.get('source') or ('NICT_auto' if source_url else 'NICT_supplied')).strip()[:80]
            if not source.upper().startswith('NICT'):source='NICT_supplied_unverified'
            out.append({'station':st,'lat':STATIONS[st][0],'lon':STATIONS[st][1],
                        'observed_at':iso(t),'fof2_mhz':round(v,4),'source':source,
                        'origin_url':source_url or None,
                        'quality':'AUTO_UNVERIFIED' if 'auto' in source.lower() else 'USER_SUPPLIED_UNVERIFIED'})
        except (ValueError,TypeError,OverflowError):errors+=1
    if errors>20 and errors>len(out):raise ValueError(f'Unrecognized rows: {errors} errors; 0/too few accepted')
    if not out:raise ValueError('No valid foF2 observation rows accepted (not a verified NICT text table)')
    unique={(v['station'],v['observed_at']):v for v in out}
    return sorted(unique.values(),key=lambda v:(v['observed_at'],v['station']))


def download_official(url):
    parts=urlparse(url)
    if (parts.scheme!='https' or parts.hostname not in ('wdc.nict.go.jp','wdc-cloud.nict.go.jp')
        or parts.username or parts.password or parts.port not in (None,443)):
        raise ValueError('Only verified official NICT HTTPS endpoint allowed')
    request=urllib.request.Request(url,headers={'User-Agent':'SWIFT-ION noncommercial research; contact project owner for details','Accept':'text/plain,text/csv'})
    # HTTPS cert validation on. Forbid unknown HTML landing pages being ingested.
    opener=urllib.request.build_opener(urllib.request.HTTPHandler(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(request,timeout=22) as response:
        if urlparse(response.url).hostname not in ('wdc.nict.go.jp','wdc-cloud.nict.go.jp'):
            raise ValueError('Off-domain redirect refused')
        data=response.read(8_000_001)
        if len(data)>8_000_000:raise ValueError('NICT text exceeds 8 MB')
        if data.lstrip().lower().startswith((b'<!doctype',b'<html')):
            raise ValueError('Landing page is HTML, not numeric NICT data')
    return data.decode('utf-8-sig')


def imported(history,now):
    cutoff=now.date()-timedelta(days=RETENTION_DAYS-1)
    result=[]
    for day in dates(cutoff,now.date()):result.extend(read_daily(history/'nict_observations',day))
    return result


def archive_observations(history,observations,now):
    by=defaultdict(list);cutoff=now.date()-timedelta(days=RETENTION_DAYS-1)
    for r in observations:
        day=parse_utc(r['observed_at']).date()
        if cutoff<=day<=now.date():by[day].append(r)
    added=0
    for day,rows in by.items():
        old={(o['station'],o['observed_at']):o for o in read_daily(history/'nict_observations',day)}
        for r in rows:
            k=(r['station'],r['observed_at'])
            if k not in old:added+=1
            old[k]=r
        write_daily(history/'nict_observations',day,sorted(old.values(),key=lambda o:(o['observed_at'],o['station'])))
    return added


def recent_issued_snapshots(history,now,lookback_days=9):
    # Allows late observational delivery while still enforcing issuance before target.
    out=[]
    for day in dates((now-timedelta(days=lookback_days)).date(),now.date()):
        for snapshot in read_daily(history/'tec_outlooks',day):
            try:
                issue=parse_utc(snapshot['metadata']['issued_at'])
                if issue<=now and snapshot.get('forecasts'):out.append(snapshot)
            except (KeyError,TypeError,ValueError):continue
    return out


def match_issued(observations,snapshots,now):
    """Four fixed station coordinates; one best issued forecast for station+target+lead.

    No hindcasting; no observed-at/issue-time leakage. 15-minute QC tolerance,
    timestamp-based matching, and close spatial match prevent fake evidence.
    """
    best={}
    for obs in observations:
        station=obs['station']; at=parse_utc(obs['observed_at'])
        if at>now+timedelta(minutes=5):continue
        for snap in snapshots:
            issue=parse_utc(snap['metadata']['issued_at'])
            if issue>=at-timedelta(minutes=30):continue
            for f in snap['forecasts']:
                try:
                    # Older snapshots might use station labels not canonical:
                    # accept only known local station coords, never arbitrary far-off sites.
                    if distance_km((obs['lat'],obs['lon']),(float(f['lat']),float(f['lon'])))>15:continue
                    target=parse_utc(f['valid_at'])
                    if not (issue<target<=now):continue
                    gap=abs((at-target).total_seconds())/60
                    if gap>15:continue
                    h=int(f['nominal_horizon_h'])
                    if h not in HORIZONS_H:continue
                    if f.get('fof2_quality','STANDARD') not in ('STANDARD','EXTENDED'):continue
                    row={'station':station,'lat':obs['lat'],'lon':obs['lon'],
                         'issued_at':iso(issue),'valid_at':iso(target),
                         'observed_at':iso(at),'nominal_horizon_h':h,
                         'time_gap_minutes':round((at-target).total_seconds()/60,2),
                         'observed_fof2_mhz':obs['fof2_mhz'],
                         'confidence':None,'quality_source':obs['quality'],
                         'fof2_quality':f.get('fof2_quality','STANDARD'),
                         'source_issued_at':snap['metadata'].get('source_issued_at'),
                         'observation_source':obs['source'],'observation_source_url':obs.get('origin_url'),
                         'kp_forecast':f.get('kp_forecast'),
                         'f107_available':f.get('f107_available'),
                         'kp_3day_confirmed':f.get('kp_3day_confirmed') is True}
                    row.update({k:f.get(k) for k in FIELDS})
                    if 'predicted_fof2_physics_mhz' not in f:
                        row['predicted_fof2_physics_mhz']=row.get('predicted_fof2_tec_mhz')
                    key=(station,iso(target),h)
                    priority=(gap,-issue.timestamp())
                    if key not in best or priority<best[key][0]:best[key]=(priority,row)
                except (KeyError,ValueError,TypeError):continue
    return [x[1] for x in best.values()]


def save_matches(history,matches,now):
    by=defaultdict(list)
    start=now.date()-timedelta(days=RETENTION_DAYS-1)
    for r in matches:
        day=parse_utc(r['valid_at']).date()
        if start<=day<=now.date():by[day].append(r)
    added=0
    for day,rows in by.items():
        old={(r['station'],r['valid_at'],int(r['nominal_horizon_h'])):r for r in read_daily(history/'nict_matches',day)}
        for r in rows:
            k=(r['station'],r['valid_at'],int(r['nominal_horizon_h']))
            prior=old.get(k)
            if prior is None:added+=1
            if prior is None or (abs(r['time_gap_minutes']),-parse_utc(r['issued_at']).timestamp()) < (abs(prior['time_gap_minutes']),-parse_utc(prior['issued_at']).timestamp()):
                old[k]=r
        write_daily(history/'nict_matches',day,sorted(old.values(),key=lambda r:(r['valid_at'],r['station'],r['nominal_horizon_h'])))
    return added


def prune(history,now):
    cutoff=now.date()-timedelta(days=RETENTION_DAYS-1)
    for name in ('nict_observations','nict_matches'):
        folder=history/name
        for p in folder.glob('*.jsonl.gz') if folder.exists() else []:
            try:d=datetime.strptime(p.name[:10],'%Y-%m-%d').date()
            except ValueError:continue
            if d<cutoff:p.unlink()


def summarize(matches):
    """Separate stage skill; missing predictions are NOT substituted by physics."""
    out={}
    stage_fields={
      'physics':'predicted_fof2_physics_mhz',
      'empirical':'predicted_fof2_empirical_mhz',
      'ai':'predicted_fof2_ai_mhz',
    }
    for st in STATIONS:
        good=[r for r in matches if r['station']==st and r.get('fof2_quality')=='STANDARD']
        out[st]={'standard_n':len(good),'stages':{}}
        for stage,field in stage_fields.items():
            d=[r[field]-r['observed_fof2_mhz'] for r in good
               if isinstance(r.get(field),(int,float)) and math.isfinite(r[field])]
            rates={str(k):round(100*sum(abs(x)<=k for x in d)/len(d),2) if d else None
                   for k in (1,2,3)}
            out[st]['stages'][stage]={
                'n':len(d),
                'hit_rate_pct':rates['2'],
                'hit_threshold_mhz':2,
                'hit_rate_by_threshold_pct':rates,
                'mae_mhz':round(sum(abs(x) for x in d)/len(d),3) if d else None,
                'rmse_mhz':round(math.sqrt(sum(x*x for x in d)/len(d)),3) if d else None,
                'bias_mhz':round(sum(d)/len(d),3) if d else None}
        out[st].update(out[st]['stages']['physics'])
        # Phys/empirical/AI are additionally compared on identical availability.
        paired=[r for r in good if all(isinstance(r.get(field),(int,float)) for field in stage_fields.values())]
        out[st]['all_three_same_observations_n']=len(paired)
    return out


def run(history,docs,import_dir=None,urls_json=None,now=None):
    now=now or datetime.now(timezone.utc);history=Path(history);docs=Path(docs)
    history.mkdir(parents=True,exist_ok=True);docs.mkdir(parents=True,exist_ok=True)
    accepted=[];failures=[];sources=[]
    if import_dir:
        folder=Path(import_dir)
        for p in sorted(folder.glob('*.csv')) if folder.exists() else []:
            try:
                if p.stat().st_size>8_000_000:raise ValueError('File exceeds 8MB')
                name=p.stem if p.stem.upper() in STATIONS or p.stem.upper() in ALIASES else None
                rows=parse_normalized_csv(p.read_text(encoding='utf-8-sig'),filename=name,now=now)
                accepted.extend(rows);sources.append(p.name)
            except (ValueError,UnicodeError) as exc:failures.append(f'{p.name}: {str(exc)[:150]}')
    if urls_json and Path(urls_json).exists():
        obj=json.loads(Path(urls_json).read_text(encoding='utf-8'))
        for k,url in obj.items():
            try:
                st=canonical(k)
                rows=parse_normalized_csv(download_official(url),filename=st,source_url=url,now=now)
                accepted.extend(rows);sources.append('NICT verified endpoint for '+st)
            except (ValueError,UnicodeError,OSError,TimeoutError) as exc:failures.append(f'{k}: {str(exc)[:150]}')
    added=archive_observations(history,accepted,now)
    prune(history,now)
    allobs=imported(history,now)
    # Match only the latest few days of arriving observations. Older matches
    # remain in their own rolling 365d archive; avoid an O(365d * snapshots)
    # recomputation on each 30-minute GitHub Actions run.
    new_since=now-timedelta(days=9)
    matches=match_issued([o for o in allobs if new_since<=parse_utc(o['observed_at'])<=now],
                         recent_issued_snapshots(history,now),now)
    newmatches=save_matches(history,matches,now)
    allmatches=[]
    for day in dates(now.date()-timedelta(days=RETENTION_DAYS-1),now.date()):
        allmatches.extend(read_daily(history/'nict_matches',day))
    latest=now-timedelta(days=7)
    published=[r for r in allobs if parse_utc(r['observed_at'])>=latest]
    with (docs/'nict_fof2_4station.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['station','time_utc','fof2_mhz','source'])
        for r in sorted(published,key=lambda x:(x['observed_at'],x['station'])):
            w.writerow([r['station'],r['observed_at'],r['fof2_mhz'],r['source']])
    report={'schema':'swift-ion-nict-four-station-v1','generated_at':iso(now),
       'status':'OBSERVATIONS_AVAILABLE' if allobs else 'AWAITING_NICT_NUMERIC_CSV',
       'hit_thresholds_mhz':[1,2,3],'main_hit_threshold_mhz':2,
       'new_observations':added,'observations_retained':len(allobs),
       'new_prospective_matches':newmatches,'prospective_matches_retained':len(allmatches),
       'last_7_days_published':len(published),'stations':summarize(allmatches),
       'sources':sources,'warnings':failures,'confidence':'NICT autoscaled numbers require original quality review; not independently verified by this code',
       'eligibility':'Only previously issued forecasts, observations <=now, nearest within ±15 min and 15 km, standard quality only for main training.',
       'notes':['NICT native archived HTML/text tables are NOT scraped without a verified numeric endpoint and parser.',
                'The official archive HTML is not a numeric API. No guessed endpoints or fabricated readings.',
                'This report is a prospective research validation, not proof of operational forecast skill.']}
    (docs/'nict_fof2_status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('NICT 4station:',report['status'],'rows',len(allobs),'new',added,'matches',len(allmatches),'new matches',newmatches,'warnings',len(failures),flush=True)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--history',type=Path,required=True)
    p.add_argument('--docs',type=Path,required=True)
    p.add_argument('--import-dir',type=Path,default=ROOT/'nict_import')
    p.add_argument('--urls-json',type=Path,default=None)
    a=p.parse_args()
    run(a.history,a.docs,a.import_dir,a.urls_json)

if __name__=='__main__':main()
