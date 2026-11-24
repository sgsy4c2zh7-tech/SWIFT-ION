"""SWIFT-ION v1.0: archived prospective IRI climatology baseline verification.

This is NOT the skill of a TEC-assimilated electron density forecast.
It compares IRI baseline values computed BEFORE an ionosonde observation to
later station data, with explicit issue time, target time and matching rules.

Inputs: docs/ionosonde_validation.json, previous GitHub Actions artifacts
Outputs: docs/station_outlook.json, docs/prospective_skill.json
Only public, non-operational and non-commercial station data are used.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import io
import json
import math
import os
from pathlib import Path
import statistics
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlparse
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PREFIX = "swift-ion-prospective-"
HORIZONS_H = (1, 3, 6, 12, 24)
SOURCE_LICENCE = "GIRO-derived via KC2G: CC BY-NC-SA 4.0; station/operator acknowledgements required"


def parse_utc(value):
    if not isinstance(value, str):
        raise ValueError('Timestamp must be an ISO8601 string')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp must include UTC offset')
    return dt.astimezone(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def next_utc_hour(target):
    dt = target.astimezone(timezone.utc)
    hour = dt.replace(minute=0, second=0, microsecond=0)
    return hour if hour == dt else hour + timedelta(hours=1)


def metrics(pairs, units):
    if not pairs:
        return {'count': 0, 'units': units, 'mae': None, 'rmse': None, 'bias': None, 'status': 'INSUFFICIENT_DATA'}
    diff = [float(a) - float(b) for a, b in pairs]
    return {'count':len(diff), 'units':units, 'mae':round(statistics.mean(abs(x) for x in diff), 4),
            'rmse':round(math.sqrt(statistics.mean(x*x for x in diff)), 4),
            'bias':round(statistics.mean(diff), 4), 'status':'DESCRIPTIVE_ONLY_SMALL_SAMPLE' if len(diff) < 10 else 'AVAILABLE'}


def build_outlook(ionosonde, iri_function, generation_started_at, horizons=HORIZONS_H, max_stations=32, *, published_at=None):
    """Make *future* IRI estimates at public station coordinates, no observation values used.

    The latest observations are used only to identify station coordinates and IDs.
    No observed foF2/hmF2 enters the prediction function.
    """
    from build_ionosphere import extract_iri_profile, diagnose

    if generation_started_at.tzinfo is None:
        raise ValueError('Generation start must contain UTC offset')
    records = ionosonde.get('stations', [])
    forecasts, errors = [], []
    count = 0
    for station in records[:max_stations]:
        try:
            lat,lon=float(station['lat']),float(station['lon'])
            name=str(station['station']).strip()
            if not name or not (-90<=lat<=90 and -180<=lon<=180):
                raise ValueError('Invalid station coordinates')
            count += 1
            for horizon in horizons:
                if horizon <= 0:
                    raise ValueError('Horizon must be strictly positive')
                valid = next_utc_hour(generation_started_at + timedelta(hours=horizon))
                if valid <= generation_started_at:
                    raise ValueError('Target is not in the future')
                try:
                    ds = iri_function(valid, [100, 2000, 25], lat, lon)
                    alt, ne = extract_iri_profile(ds)
                    d = diagnose(alt, ne)
                    forecasts.append({'station': name, 'lat': round(lat, 5), 'lon': round(lon, 5),
                        'valid_at': iso(valid), 'nominal_horizon_h': horizon,
                        'actual_lead_h': None,
                        'fof2_mhz': d['fof2_mhz'], 'hmf2_km': d['hmf2_km'],
                        'peak_at_boundary': bool(d['peak_at_boundary']),
                        'method': 'IRI_AT_STATION_FUTURE_TIME_NO_OBSERVATION_ASSIMILATION'})
                except Exception as ex:
                    errors.append({'station':name,'horizon_h':horizon,'reason':str(ex)[:160]})
        except (ValueError, TypeError, KeyError) as ex:
            errors.append({'station':'INVALID_STATION','reason':str(ex)[:160]})
    # Issue time is when all computations are finished, never their start time.
    # The workflow may take minutes to upload the artifact, so allow a buffer.
    completed = published_at or datetime.now(timezone.utc)
    if completed.tzinfo is None or completed < generation_started_at:
        raise ValueError('Completion time must be aware and after generation start')
    candidates = len(forecasts)
    forecasts = [f for f in forecasts if parse_utc(f['valid_at']) >= completed + timedelta(minutes=30)]
    for f in forecasts:
        f['actual_lead_h'] = round((parse_utc(f['valid_at'])-completed).total_seconds()/3600,4)
    if not records:
        status = 'NO_STATION_CATALOG'
    elif not forecasts:
        status = 'NO_VALID_FUTURE_TARGETS' if candidates else 'IRI_COMPUTATION_FAILED'
    else:
        status = 'AVAILABLE'
    return {'metadata':{'schema':'swift-ion-prospective-iri-baseline-v1',
                'model':'IRI-2020 climatological baseline',
                'generation_started_at':iso(generation_started_at),
                'issued_at':iso(completed),
                'minimum_target_buffer_minutes':30, 'source_station_catalog':'KC2G GIRO-derived station list',
                'station_catalog_time':ionosonde.get('metadata',{}).get('generated_at'),
                'licence':SOURCE_LICENCE,
                'is_tec_assimilated':False, 'is_verified_prediction':False,
                'description':'IRI for future valid times at named station coordinates. This is a prospective climatology baseline, not an operational forecast.'},
            'status':status, 'station_count':count, 'forecasts':forecasts,
            'omitted_near_term_after_completion':candidates-len(forecasts),
            'failures':len(errors),'error_samples':errors[:12]}


def _angular_distance_km(a, b):
    lat1,lon1=math.radians(float(a['lat'])),math.radians(float(a['lon']))
    lat2,lon2=math.radians(float(b['lat'])),math.radians(float(b['lon']))
    z=math.sin(lat1)*math.sin(lat2)+math.cos(lat1)*math.cos(lat2)*math.cos(lon1-lon2)
    return 6371*math.acos(max(-1,min(1,z)))


def score_history(observations, snapshots, now, *, max_time_gap_min=30, min_lead_minutes=30):
    """Strictly retrospective: issue < target <= observation receipt time.

    Compare at an unchanged station identity and within 25 km / time gap.
    Score at most one prior forecast per station, model horizon and observation.
    Do not compare the current run's outlook (not in snapshots).
    """
    recent_obs=observations.get('stations', [])
    result=[]
    skips=defaultdict(int)
    for obs in recent_obs:
        try:
            obs_at=parse_utc(obs['observed_at'])
            if obs_at > now+timedelta(minutes=5):
                skips['observation_in_future']+=1;continue
            # Exclude unknown/low station confidence from headline scientific scores.
            if obs.get('confidence_known') is not True or float(obs.get('confidence') or 0) < 70:
                skips['confidence_unverified']+=1;continue
            station=str(obs['station'])
        except (KeyError, ValueError, TypeError):
            skips['bad_observation']+=1;continue
        for snapshot in snapshots:
            try:
                issued=parse_utc(snapshot['metadata']['issued_at'])
            except (KeyError,ValueError,TypeError):
                skips['untrusted_issue_time']+=1;continue
            if snapshot.get('metadata',{}).get('schema') != 'swift-ion-prospective-iri-baseline-v1':
                skips['unknown_schema']+=1;continue
            if issued >= obs_at-timedelta(minutes=min_lead_minutes) or issued > now:
                skips['issued_too_late']+=1;continue
            for f in snapshot.get('forecasts',[]):
                if f.get('station') != station:
                    continue
                try:
                    valid=parse_utc(f['valid_at'])
                    if valid <= issued:
                        skips['nonprospective']+=1;continue
                    if valid > now or abs((obs_at-valid).total_seconds()) > max_time_gap_min*60:
                        skips['wrong_valid_time']+=1;continue
                    if _angular_distance_km(f,obs) > 25:
                        skips['station_coordinates_changed']+=1;continue
                    horizon=int(f['nominal_horizon_h'])
                    if horizon not in HORIZONS_H:
                        skips['unexpected_horizon']+=1;continue
                except (KeyError,ValueError,TypeError):
                    skips['bad_forecast_record']+=1;continue
                key=(station,obs['observed_at'],horizon)
                entry={'station':station,'lat':float(obs['lat']),'lon':float(obs['lon']),
                       'observed_at':iso(obs_at),'issued_at':iso(issued),'valid_at':iso(valid),
                       'nominal_horizon_h':horizon,'actual_lead_h':f.get('actual_lead_h'),
                       'time_gap_minutes':round((obs_at-valid).total_seconds()/60,2),
                       'confidence':obs['confidence'],
                       'observed_fof2_mhz':obs.get('fof2_mhz'),
                       'predicted_fof2_mhz':f.get('fof2_mhz'),
                       'observed_hmf2_km':obs.get('hmf2_km'),
                       'predicted_hmf2_km':None if f.get('peak_at_boundary') else f.get('hmf2_km'),
                       'hmf2_peak_at_boundary':bool(f.get('peak_at_boundary'))}
                # Stable dedup with latest issuance (does not double-count archived runs).
                result.append((key,entry))
    best={}
    for key, entry in result:
        prior=best.get(key)
        if prior is None or (entry['issued_at'], -abs(entry['time_gap_minutes'])) > (prior['issued_at'], -abs(prior['time_gap_minutes'])):
            best[key]=entry
    matched=sorted(best.values(),key=lambda x:(x['nominal_horizon_h'],x['station']))
    groups={}
    for h in HORIZONS_H:
        sub=[r for r in matched if r['nominal_horizon_h']==h]
        fp=[(float(r['predicted_fof2_mhz']),float(r['observed_fof2_mhz']))
            for r in sub if _valid(r.get('predicted_fof2_mhz')) and _valid(r.get('observed_fof2_mhz'))]
        hp=[(float(r['predicted_hmf2_km']),float(r['observed_hmf2_km']))
            for r in sub if _valid(r.get('predicted_hmf2_km')) and _valid(r.get('observed_hmf2_km'))]
        groups[str(h)]={'matched_stations':len(sub),'fof2':metrics(fp,'MHz'), 'hmf2':metrics(hp,'km')}
    return {'metadata':{'schema':'swift-ion-prospective-evaluation-v1','generated_at':iso(now),
                'forecast_type':'PROSPECTIVELY_ISSUED_IRI_CLIMATOLOGY_BASELINE',
                'is_swifttec_layer_forecast_skill':False,
                'comparison':'IRI baseline issued before observation, matched by station and approximate UTC validity',
                'licence':SOURCE_LICENCE,
                'criteria':{'max_station_separation_km':25,'max_utc_difference_minutes':max_time_gap_min,
                            'min_issue_lead_minutes':min_lead_minutes,'minimum_confidence':70},
                'warning':'Pre-issue IRI baseline vs ionosonde, not skill of TEC-constrained Ne or a validated storm-time forecast. Sparse matches and source licensing limit conclusions.'},
            'status':'AVAILABLE' if matched else 'PENDING_HISTORY_OR_NO_EXACT_MATCHES',
            'snapshot_count':len(snapshots), 'observations_considered':len(recent_obs),
            'matched_count':len(matched), 'horizons':groups, 'matches':matched[:100],
            'skipped':dict(skips)}


def _valid(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


class SafeRedirect(HTTPRedirectHandler):
    """Never forward the workflow token to GitHub's artifact storage redirect."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected=super().redirect_request(req,fp,code,msg,headers,newurl)
        if redirected is not None and (urlparse(newurl).hostname != 'api.github.com' or urlparse(newurl).scheme != 'https'):
            for field in list(redirected.headers):
                if field.lower() == 'authorization':
                    del redirected.headers[field]
            for field in list(redirected.unredirected_hdrs):
                if field.lower() == 'authorization':
                    del redirected.unredirected_hdrs[field]
        return redirected


def _get(url, token, maxbytes):
    if urlparse(url).hostname != 'api.github.com' or not url.startswith('https://'):
        raise ValueError('Authorized requests may only start at api.github.com HTTPS')
    req=Request(url, headers={'Authorization':'Bearer '+token,
                              'Accept':'application/vnd.github+json',
                              'X-GitHub-Api-Version':'2022-11-28',
                              'User-Agent':'SWIFT-ION-prospective-research'})
    with build_opener(SafeRedirect()).open(req,timeout=25) as response:
        data=response.read(maxbytes+1)
    if len(data)>maxbytes:
        raise ValueError('GitHub API download size limit exceeded')
    return data


def fetch_previous_artifacts(repo, token, *, max_artifacts=24):
    """Read previous public-workflow artifacts via read-only GitHub REST API.

    Network failures lead to explicit pending status and never create fake scores.
    GitHub Actions artifact retention is 7 days in the workflow.
    """
    if not token or not repo or repo.count('/')!=1:
        return [], 'GITHUB_ACTIONS_TOKEN_NOT_AVAILABLE'
    snapshots=[]
    try:
        listed=json.loads(_get(f'https://api.github.com/repos/{repo}/actions/artifacts?per_page=100',token,1_000_000))
        candidates=[a for a in listed.get('artifacts',[]) if isinstance(a.get('name'),str)
                    and a['name'].startswith(ARTIFACT_PREFIX) and not a.get('expired',False)]
        for a in sorted(candidates,key=lambda x:x.get('created_at',''),reverse=True)[:max_artifacts]:
            try:
                blob=_get(f'https://api.github.com/repos/{repo}/actions/artifacts/{int(a["id"])}/zip',token,3_000_000)
                with zipfile.ZipFile(io.BytesIO(blob)) as bundle:
                    paths=[x for x in bundle.namelist() if Path(x).name=='station_outlook.json']
                    if len(paths)!=1:
                        continue
                    if bundle.getinfo(paths[0]).file_size > 3_000_000:
                        continue
                    with bundle.open(paths[0]) as f:
                        snap=json.load(f)
                if snap.get('metadata',{}).get('schema')=='swift-ion-prospective-iri-baseline-v1':
                    snapshots.append(snap)
            except (ValueError,OSError,zipfile.BadZipFile,KeyError,HTTPError,URLError,json.JSONDecodeError) as ex:
                print(f'Archive {a.get("id")} unavailable: {str(ex)[:100]}',flush=True)
    except (ValueError,OSError,HTTPError,URLError,json.JSONDecodeError) as ex:
        return [], 'HISTORY_API_UNAVAILABLE: '+str(ex)[:150]
    return snapshots, 'HISTORY_AVAILABLE' if snapshots else 'NO_PRIOR_ARTIFACTS_YET'


def save(path, payload):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix('.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8')
    temp.replace(p)


def run(obs_path, outlook_path, score_path, *, now=None, iri_function=None, prior_snapshots=None, history_status=None, published_at=None):
    now=now or datetime.now(timezone.utc)
    report=json.loads(Path(obs_path).read_text(encoding='utf-8'))
    if prior_snapshots is None:
        prior_snapshots,history_status=fetch_previous_artifacts(os.getenv('GITHUB_REPOSITORY',''),
                                                                 os.getenv('GH_TOKEN',''))
    skill=score_history(report,prior_snapshots,now)
    skill['history_status']=history_status or 'TEST_FIXTURE'
    if skill['status']=='PENDING_HISTORY_OR_NO_EXACT_MATCHES' and history_status and history_status.startswith('HISTORY_API_UNAVAILABLE'):
        skill['status']='HISTORY_UNAVAILABLE'
    # A snapshot is issued only AFTER computing future values; never backdate it.
    if iri_function is None:
        from iri2020 import IRI as iri_function
    future=build_outlook(report,iri_function,now,published_at=published_at)
    save(outlook_path,future)
    save(score_path,skill)
    print('Prospective IRI issued:',future['station_count'],'stations;',len(future['forecasts']),'predictions')
    print('Retrospective score:',skill['status'],'previous artifacts:',len(prior_snapshots),'matches:',skill['matched_count'])
    return future,skill


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observations',type=Path,default=ROOT/'docs/ionosonde_validation.json')
    parser.add_argument('--outlook',type=Path,default=ROOT/'docs/station_outlook.json')
    parser.add_argument('--skill',type=Path,default=ROOT/'docs/prospective_skill.json')
    args=parser.parse_args()
    run(args.observations,args.outlook,args.skill)
