"""Fetch current NOAA SWPC G/S/R indices. Not a forecast, no fabricated fallback."""
from __future__ import annotations
import argparse,json,urllib.request
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
URL='https://services.swpc.noaa.gov/products/noaa-scales.json'

def extract(data, fetched):
    if not isinstance(data,dict) or not isinstance(data.get('0'),dict):
        raise ValueError('NOAA-scales current record not found')
    src=data['0'];scales={}
    for k in ('G','S','R'):
        entry=src.get(k)
        if not isinstance(entry,dict): raise ValueError('Missing current '+k+' scale')
        raw=entry.get('Scale')
        try:v=int(raw)
        except (TypeError,ValueError):raise ValueError('Invalid '+k+' scale')
        if not 0<=v<=5:raise ValueError('Scale exceeds 0..5 range')
        scales[k]=v
    datestamp=src.get('DateStamp');timestamp=src.get('TimeStamp')
    return {'status':'available','source_at_utc':f'{datestamp}T{timestamp}Z' if datestamp and timestamp else None,
            'current_scales':scales,'fetched_at_utc':fetched,'source_url':URL,
            'interpretation':'CURRENT NOAA G/S/R category only, not route-time forecast; cannot determine HF link availability, radiation dose or GNSS outages.'}

def build(out, fetch=None):
    now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    result={'status':'unavailable','fetched_at_utc':now,'source_url':URL,
            'current_scales':None,'source_at_utc':None,
            'reason':'NOAA source unavailable; no stale/synthetic substitute',
            'interpretation':'Current observations only; no route-time or system availability prediction.'}
    try:
        if fetch is None:
            req=urllib.request.Request(URL,headers={'User-Agent':'SWIFT-ION public research (no personal data)'})
            with urllib.request.urlopen(req,timeout=18) as r:body=r.read(100_001)
            if len(body)>100_000:raise ValueError('Excessive NOAA payload size')
            data=json.loads(body)
        else:data=fetch()
        result=extract(data,now)
    except Exception as e:
        result['reason']=type(e).__name__+': '+str(e)[:110]
        print('NOAA nowcast unavailable:',result['reason'],flush=True)
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'docs/space_weather.json');a=ap.parse_args()
    build(a.out)
