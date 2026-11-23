"""Optional, issue-time NOAA solar/geomagnetic predictors. Never block main workflow.
NOAA Kp *predicted* values only are matched to future valid time; F10.7 is a
past/now observed proxy held constant (persistence), NEVER an F10.7 forecast.
"""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
import argparse,json,urllib.request
from pathlib import Path
from fof2_ml import time_utc,num

K_URL='https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json'
F_URL='https://services.swpc.noaa.gov/json/f107_cm_flux.json'

def parse_kp(items,now):
    if not isinstance(items,list):return []
    out=[]
    for r in items:
        if not isinstance(r,dict) or r.get('observed')!='predicted':continue
        try:
            t=time_utc(str(r['time_tag'])+'Z' if len(str(r['time_tag']))==19 else r['time_tag'])
            k=num(r['kp'],0,9)
            if k is not None and now-timedelta(minutes=15)<=t<=now+timedelta(hours=96):out.append({'valid_from_utc':t.isoformat().replace('+00:00','Z'),'kp':k})
        except (KeyError,TypeError,ValueError):continue
    return sorted(out,key=lambda v:v['valid_from_utc'])

def parse_f107(items,now):
    if not isinstance(items,list):return None
    out=[]
    for r in items:
        if not isinstance(r,dict):continue
        try:
            t=time_utc(str(r.get('time_tag') or r.get('time'))+'Z' if len(str(r.get('time_tag') or r.get('time')))==19 else r.get('time_tag') or r.get('time'))
            flux=num(r.get('flux') if r.get('flux') is not None else r.get('f10.7'),50,400)
            if flux is not None and now-timedelta(days=4)<=t<=now:out.append((t,flux))
        except (KeyError,TypeError,ValueError):continue
    if not out:return None
    t,v=max(out)
    return {'value_sfu':v,'observed_at_utc':t.isoformat().replace('+00:00','Z'),'use':'OBSERVED_PERSISTENCE_NOT_FORECAST'}

def same_issue_swifttec_kp(filename,now):
    """Audited NOAA 3-day slots exported from the *same* upstream TEC run."""
    if not filename or not Path(filename).is_file():return None
    data=json.loads(Path(filename).read_text(encoding='utf-8'))
    if data.get('schema')!='swift-ion-swifttec-issue-kp3day-v1' or data.get('source_mode')!='SWIFTTEC_SAME_ISSUE_NOAA_3DAY':return None
    generated=time_utc(data['generated_at'])
    if generated>now+timedelta(minutes=5) or now-generated>timedelta(hours=2):return None
    first=time_utc(data['valid_from_utc']);last=time_utc(data['valid_until_exclusive_utc'])
    if last-first!=timedelta(days=3):return None
    slots=data.get('slots') or []
    if len(slots)!=24:return None
    results=[]
    for row in slots:
        t=time_utc(row['valid_from_utc']);value=num(row.get('kp'),0,9)
        if value is None or t<first or not t<last or t.minute or t.second or (t-first).total_seconds()%10800: return None
        results.append({'valid_from_utc':t.isoformat().replace('+00:00','Z'),'kp':value})
    if sorted(x['valid_from_utc'] for x in results)!=[ (first+timedelta(hours=3*i)).isoformat().replace('+00:00','Z') for i in range(24) ]:return None
    return results


def build(now,fetch=None,swiftec_kp=None):
    fetch=fetch or _fetch_json
    ret={'schema':'swift-ion-fof2-driver-v1','fetched_at':now.isoformat().replace('+00:00','Z'),
         'kp_predicted':[],'f107_recent_observed':None,'errors':[],
         'kp_source':K_URL,'f107_source':F_URL}
    for what,url,parser,key in [('kp',K_URL,parse_kp,'kp_predicted'),('f107',F_URL,parse_f107,'f107_recent_observed')]:
        try:ret[key]=parser(fetch(url),now)
        except (OSError,ValueError,TypeError,KeyError,TimeoutError) as exc:ret['errors'].append(what+': '+str(exc)[:90])
    try:
        aligned=same_issue_swifttec_kp(swiftec_kp,now)
        if aligned is not None:
            ret['kp_predicted']=aligned
            ret['kp_source']='SWIFT-TEC SAME-ISSUE NOAA 3-day geomagnetic forecast'
            ret['kp_source_mode']='SWIFTTEC_SAME_ISSUE_NOAA_3DAY'
        else:ret['kp_source_mode']='INDEPENDENT_NOAA_FALLBACK_OR_UNAVAILABLE'
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as exc:
        ret['kp_source_mode']='INDEPENDENT_NOAA_FALLBACK_OR_UNAVAILABLE'
        ret['errors'].append('upstream_kp_provenance: '+str(exc)[:100])
    return ret

def _fetch_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':'SWIFT-ION noncommercial research'})
    with urllib.request.urlopen(req,timeout=15) as r:
        raw=r.read(300_001)
        if len(raw)>300_000:raise ValueError('Source too large')
    return json.loads(raw)

def drivers_at(payload,valid_at,now):
    if not isinstance(payload,dict) or payload.get('schema')!='swift-ion-fof2-driver-v1':return None,None
    target=time_utc(valid_at)
    # Only forecaster-labeled predicted Kp applicable to 3h bin. Prevent reuse
    # of an observed Kp value that was not yet available at forecast issuance.
    matches=[]
    for row in payload.get('kp_predicted') or []:
        try:
            at=time_utc(row['valid_from_utc']);k=num(row['kp'],0,9)
            if k is not None and at<=target<at+timedelta(hours=3):matches.append((at,k))
        except (KeyError,TypeError,ValueError):continue
    kp=max(matches)[1] if matches else None
    f=payload.get('f107_recent_observed') or {}
    try:
        f_at=time_utc(f['observed_at_utc']);fv=num(f['value_sfu'],50,400)
        # A 4-day-old F10.7 observation should not be advertised as future F10.7.
        f107=fv if now>=f_at and now-f_at<timedelta(days=4) else None
    except (KeyError,TypeError,ValueError):f107=None
    return kp,f107

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--swiftec-kp',type=Path,default=None);args=p.parse_args()
    result=build(datetime.now(timezone.utc),swiftec_kp=args.swiftec_kp);args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    print('foF2 drivers: predicted Kp bins',len(result['kp_predicted']),'recent observed F10.7',result['f107_recent_observed'] is not None,'warnings',len(result['errors']))

if __name__=='__main__':main()
