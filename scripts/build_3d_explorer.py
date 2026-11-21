"""3-D IRI research visualization export, with independently timestamped ISEE Japan VTEC.

Inputs:
  docs/ionosphere.json              Existing *real IRI* sampled global profile output
  _upstream_swifttec/docs/data/isee_tec/index.json, timestamped frame JSON
Outputs:
  docs/explorer_data.json

- ISEE is a VTEC reference product, NOT electron density with height.
- Regional Ne(h) is calculated via a fresh IRI call at EXACTLY the archived ISEE UTC.
- Missing ISEE or regional IRI does not fake data or erase the valid global output.
- Source time and latency are retained so old ISEE frames cannot masquerade as nowcast.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALTITUDES = (100, 150, 200, 250, 300, 350, 400, 500, 600, 800, 1000)
# Fixed, openly described sampling lattice. Non-operational, no private coordinates.
JAPAN_LATITUDES = (25.0, 29.0, 32.5, 35.7, 39.0, 42.5, 45.0)
JAPAN_LONGITUDES = (123.0, 127.0, 130.5, 134.5, 139.7, 144.0, 148.0)
JAPAN_SITE_ANCHORS = ((43.06,141.35),(38.27,140.87),(35.68,139.76),
                      (35.18,136.91),(34.70,135.50),(34.40,132.46),
                      (33.59,130.40),(31.60,130.56),(26.21,127.68))


def utc(s: str) -> datetime:
    dt = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('UTC offset required')
    return dt.astimezone(timezone.utc)


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def finite_number(v, low=0.0, high=1e16):
    if isinstance(v, bool) or v is None:
        return None
    try: x = float(v)
    except (TypeError, ValueError): return None
    return x if math.isfinite(x) and low <= x <= high else None


def profile_at(alts, ne, height):
    if not (len(alts) == len(ne) and len(alts) >= 2):
        raise ValueError('Invalid IRI profile dimensions')
    if height < alts[0] or height > alts[-1]:
        return None
    for k in range(1,len(alts)):
        if alts[k] < height:
            continue
        if alts[k] <= alts[k-1]: raise ValueError('IRI altitude not increasing')
        t=(height-alts[k-1])/(alts[k]-alts[k-1])
        return (1-t)*ne[k-1] + t*ne[k]
    return ne[-1]


def site(lat, lon, alt, ne, method, diag=None):
    if not (-90<=lat<=90 and -180<=lon<=180): raise ValueError('Invalid site coordinates')
    arr=[]
    for h in ALTITUDES:
        n=profile_at(alt, ne, h)
        arr.append(round(math.log10(max(n,1)),4) if n is not None and n>=0 and math.isfinite(n) else None)
    if sum(x is not None for x in arr)<len(ALTITUDES):
        raise ValueError('IRI profile has no complete 100–1000 km coverage')
    return {'lat':round(lat,3),'lon':round(lon,3), 'ne_log10_m3':arr,
            'method':method,'iri':diag or {}}


def build_global(ion):
    if ion.get('metadata',{}).get('is_forecast') is not False:
        raise ValueError('Global input must be explicitly labeled as IRI climatology')
    out=[]
    for frame in ion.get('frames',[]):
        ir=[]
        for c in frame.get('cells',[]):
            try:
                p=c['profile']
                one=site(float(c['lat']),float(c['lon']),
                               [float(h) for h in p['alt_km']], [float(n) for n in p['ne_m3']],
                               'IRI_RUN',c.get('iri'))
                tec=finite_number(c.get('vtec_swifttec_tecu'),0,200)
                if tec is not None: one['vtec_swifttec_tecu']=round(tec,3)
                ir.append(one)
            except (ValueError,KeyError,TypeError):
                continue
        if len(ir)<4: raise ValueError('Insufficient IRI global real profiles')
        out.append({'valid_at':iso(utc(frame['valid_at'])),'sites':ir,
                    'sample_count':len(ir),'source_label':'IRI-2020 sampled global climatology'})
    if not out: raise ValueError('No valid global IRI frames')
    return out


def latest_halfhour_entries(archive: Path, count: int):
    """Select only archived 00/30 minute timestamps from a read-only index.

    Nearest-time approximation is forbidden; each model frame is recomputed at
    exactly that ISEE observation time.
    """
    idx_path=archive/'index.json'
    if not idx_path.is_file(): return None, []
    if idx_path.stat().st_size>4_000_000: raise ValueError('ISEE index larger than 4 MB')
    index=json.loads(idx_path.read_text(encoding='utf-8'))
    if index.get('quantity')!='VTEC' or index.get('units')!='TECU':
        raise ValueError('Unexpected ISEE quantity/units')
    chosen={}
    for item in index.get('frames',[]):
        try:
            dt=utc(item['time_utc'])
            name=item['file']
            if dt.minute not in (0,30) or dt.second!=0:
                continue
            if not isinstance(name,str) or not name.endswith('.json'):
                continue
            resolved=(archive/name).resolve()
            if not resolved.is_relative_to(archive.resolve()) or not resolved.is_file():
                continue
            chosen[iso(dt)]=dict(item)
        except (KeyError,TypeError,ValueError,OSError):
            continue
    return index,[chosen[k] for k in sorted(chosen)[-count:]]


def read_isee_grid(archive, entry):
    p=(archive/entry['file']).resolve()
    if not p.is_relative_to(archive.resolve()): raise ValueError('Unsafe ISEE path')
    if p.stat().st_size>3_000_000: raise ValueError('ISEE grid file too large')
    doc=json.loads(p.read_text(encoding='utf-8'))
    if iso(utc(doc['time_utc']))!=iso(utc(entry['time_utc'])):
        raise ValueError('ISEE timestamp mismatch')
    if doc.get('quantity')!='VTEC' or doc.get('units')!='TECU':
        raise ValueError('Unexpected ISEE data units')
    lats=doc['lat_arr'];lons=doc['lon_arr'];grid=doc['grid']
    if not (5<=len(lats)<=400 and 5<=len(lons)<=500 and len(grid)==len(lats)):
        raise ValueError('Invalid ISEE grid size')
    lat=[float(x) for x in lats];lon=[float(x) for x in lons]
    if any(not 20<=x<=50 for x in lat) or any(not 115<=x<=160 for x in lon):
        raise ValueError('ISEE region unexpectedly changed')
    if any(b<=a for a,b in zip(lat,lat[1:])) or any(b<=a for a,b in zip(lon,lon[1:])):
        raise ValueError('ISEE grid coordinate axes are not ascending')
    values=[]
    for row in grid:
        if len(row)!=len(lon): raise ValueError('Ragged ISEE rows')
        values.append([round(x,3) if (x:=finite_number(z,0,250)) is not None else None for z in row])
    if sum(x is not None for r in values for x in r)<50:
        raise ValueError('Too few ISEE valid VTEC cells')
    return {'lat_arr':lat,'lon_arr':lon,'grid_tecu':values,
            'source_product':doc.get('source_product'),'source_file':doc.get('source_file'),
            'source_url':doc.get('source_url'), 'units':'TECU'}


def sample_lattice(limit):
    candidates=[(lat,lon) for lat in JAPAN_LATITUDES for lon in JAPAN_LONGITUDES]
    chosen=list(JAPAN_SITE_ANCHORS[:limit])
    # Distribute remaining IRI sites across the region by max-min separation.
    # Include named cities first, then avoid row-major sampling bias.
    while len(chosen)<limit and candidates:
        x=max(candidates,key=lambda p:(min((p[0]-q[0])**2+(p[1]-q[1])**2 for q in chosen),-p[0],-p[1]))
        chosen.append(x); candidates.remove(x)
    return chosen


def default_iri_provider(time,lat,lon):
    from iri2020 import IRI
    from build_ionosphere import extract_iri_profile, diagnose
    a,n=extract_iri_profile(IRI(time,[100,2000,25],lat,lon))
    return a,n,diagnose(a,n)


def build(ionosphere,isee_archive,output,*,regional_sites=36,max_isee_frames=3,iri_provider=None, now=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None: raise ValueError('Must pass timezone aware now')
    ion=json.loads(Path(ionosphere).read_text(encoding='utf-8'))
    global_frames=build_global(ion)
    base=Path(isee_archive)
    index,entries=latest_halfhour_entries(base,max_isee_frames)
    japan={'status':'UNAVAILABLE','frames':[], 'region':None,
           'note':'ISEE VTEC is an independent historical observation-type product, not Ne(h) or a current forecast.'}
    if index:
        japan['region']=index.get('region')
        japan['index_updated_utc']=index.get('updated_utc')
        japan['latest_source_hour_utc']=index.get('latest_source_hour_utc')
        japan['source_product']=index.get('source_product','ISEE Japan VTEC')
    failures=[]
    for entry in entries:
        try:
            dt=utc(entry['time_utc'])
            if dt>now: raise ValueError('Future-dated ISEE reference rejected')
            grid=read_isee_grid(base,entry)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            failures.append('ISEE frame invalid: '+str(exc)[:110]);continue
        iri_sites=[]
        coords=sample_lattice(regional_sites)
        for lat,lon in coords:
            try:
                provider=iri_provider or default_iri_provider
                al,ne,diag=provider(dt,lat,lon)
                iri_sites.append(site(lat,lon,al,ne,'IRI_RUN_AT_ISEE_UTC',diag))
            except Exception as exc:
                failures.append(f'IRI {iso(dt)} ({lat},{lon}): {str(exc)[:90]}')
        japan['frames'].append({'valid_at':iso(dt),'vtec':grid,
                                'iri_sites':iri_sites,'iri_sites_requested':len(coords),
                                'iri_sites_computed':len(iri_sites),
                                'source_age_hours':round((now-dt).total_seconds()/3600,2)})
    if japan['frames']:
        japan['status']='AVAILABLE' if any(len(x['iri_sites'])>=4 for x in japan['frames']) else 'VTEC_ONLY_IRI_FAILED'
        japan['observation_lag_hours']=japan['frames'][-1]['source_age_hours']
    else:
        japan['note']='ISEE read-only archive had no eligible (UTC :00/:30) valid frame; no Japan observation fabricated.'
    japan['failed_operations']=len(failures)
    japan['error_examples']=failures[:4]
    result={'schema':'swift-ion-explorer-v1.4', 'metadata':{
        'generated_at':iso(now),'altitudes_km':list(ALTITUDES),
        'electron_density_units':'log10(electrons/m3)',
        'source_global':'IRI-2020 climatology (real sparse IRI site calculations)',
        'source_japan':'ISEE Japan AGRID2 VTEC archived observations + IRI-2020 computed at matching UTC',
        'is_forecast_skill':False,'is_observed_3d_density':False,
        'warnings':['Neither IRI nor ISEE VTEC alone is observed 3-D electron density.',
          'Cross sections are sparse-space IDW interpolations of IRI model profiles.',
          'Global and Japan data use separate dates. Do NOT compare without matching UTC.',
          'ISEE may be several days late; the shown source UTC and age are authoritative.',
          'This is non-operational, public-data research visualization.']},
       'global_frames':global_frames, 'japan':japan}
    p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8')
    tmp.replace(p)
    print('Explorer export:',len(global_frames),'global frames,',len(japan['frames']),'Japan ISEE frames,',
          sum(f['iri_sites_computed'] for f in japan['frames']),'matched UTC IRI sites, status',japan['status'],flush=True)
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--ionosphere',type=Path,default=ROOT/'docs/ionosphere.json')
    ap.add_argument('--isee-archive',type=Path,default=ROOT/'_upstream_swifttec/docs/data/isee_tec')
    ap.add_argument('--output',type=Path,default=ROOT/'docs/explorer_data.json')
    ap.add_argument('--regional-sites',type=int,default=36)
    ap.add_argument('--max-isee-frames',type=int,default=3)
    a=ap.parse_args()
    if not 4<=a.regional_sites<=100 or not 1<=a.max_isee_frames<=12:
        ap.error('Invalid regional-sites / max-isee-frames')
    build(a.ionosphere,a.isee_archive,a.output,regional_sites=a.regional_sites,max_isee_frames=a.max_isee_frames)
