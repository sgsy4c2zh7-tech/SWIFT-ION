"""SWIFT-ION: prospective IRI baseline + TEC-linked *experimental scenario*.

All future IRI reference profiles are computed at explicit future UTC anchors;
30-minute values are linearly interpolated between those IRI computations.
SWIFT-TEC native 30-minute VTEC forecast supplies the *column* constraint.
Uniform Ne(h) scaling is an intentionally restricted sensitivity experiment,
not a unique inverse solution, not an assimilative electron-density model, and
not a validated foF2 forecast.

No synthetic data, no silent fill of missing VTEC/IRI, no historical skill claims.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PROFILE_ALTITUDES = list(range(100, 2001, 25))
DISPLAY_ALTITUDES = [100,150,200,250,300,350,400,500,600,800,1000]
JAPAN_SITES = [(43.06,141.35),(38.27,140.87),(35.68,139.76),
               (35.18,136.91),(34.70,135.50),(33.59,130.40),
               (26.21,127.68)]
SCHEMA = 'swift-ion-iri-tec-forecast-v1'


def utc(t):
    d=datetime.fromisoformat(str(t).replace('Z','+00:00'))
    if d.tzinfo is None:
        raise ValueError('UTC timezone is required')
    return d.astimezone(timezone.utc)


def iso(t):
    return t.astimezone(timezone.utc).isoformat().replace('+00:00','Z')


def finite(n, low=0, high=1e16):
    if isinstance(n,bool) or n is None: return None
    try: v=float(n)
    except (TypeError, ValueError): return None
    return v if math.isfinite(v) and low <= v <= high else None


def distance_km(p, q):
    a,b=map(math.radians,p);c,d=map(math.radians,q)
    z=math.sin(a)*math.sin(c)+math.cos(a)*math.cos(c)*math.cos(b-d)
    return 6371*math.acos(max(-1,min(1,z)))


def locations(global_json, max_sites=16):
    if max_sites<4 or max_sites>36: raise ValueError('max-sites must be 4..36')
    seen=set();out=[]
    for lat,lon in JAPAN_SITES[:min(max_sites, len(JAPAN_SITES))]:
        out.append((lat,lon));seen.add((lat,lon))
    cells=global_json.get('frames',[{}])[0].get('cells',[])
    candidates=[]
    for c in cells:
        try:
            lat,lon=float(c['lat']),float(c['lon'])
        except (TypeError,ValueError,KeyError): continue
        if not (-90<=lat<=90 and -180<=lon<=180): continue
        if (lat,lon) not in seen:
            candidates.append((lat,lon));seen.add((lat,lon))
    while len(out)<max_sites and candidates:
        chosen=max(candidates,key=lambda p:min(distance_km(p,q) for q in out))
        out.append(chosen);candidates.remove(chosen)
    return out


def find_bracket(axis, x):
    if not axis or x<axis[0] or x>axis[-1]:return None
    if len(axis)<2:return None
    lo,hi=0,len(axis)-1
    while hi-lo>1:
        m=(lo+hi)//2
        if axis[m]<=x:lo=m
        else:hi=m
    f=(x-axis[lo])/(axis[hi]-axis[lo]) if axis[hi]!=axis[lo] else 0
    return lo,hi,f


def bilinear_vtec(row, lats, lons, lat, lon, scale=10):
    a=find_bracket(lats,lat); b=find_bracket(lons,lon)
    if not a or not b:return None
    i,j,fy=a; k,m,fx=b; nx=len(lons)
    values=[row[i*nx+k],row[i*nx+m],row[j*nx+k],row[j*nx+m]]
    if any(finite(v,0,10000) is None for v in values):return None
    ul,ur,ll,lr=(float(x)/scale for x in values)
    return (1-fy)*((1-fx)*ul+fx*ur)+fy*((1-fx)*ll+fx*lr)


def profile_iri(provider, t, lat, lon):
    result=provider(t,lat,lon)
    if isinstance(result, tuple) and len(result)==2:
        alt,ne=result
    else:raise ValueError('IRI provider must return (altitude_km, density_m-3)')
    if len(alt)!=len(ne) or len(alt)<10:raise ValueError('Bad IRI profile length')
    alt=[float(v) for v in alt];ne=[float(v) for v in ne]
    if any(not math.isfinite(x) for x in alt) or any(b<=a for a,b in zip(alt,alt[1:])):
        raise ValueError('IRI altitudes invalid')
    if alt[0]>100 or alt[-1]<2000 or any(v<0 or not math.isfinite(v) for v in ne):
        raise ValueError('IRI density/range invalid')
    # Re-sample fixed 25-km altitude support (not interpolation of a larger vertical range).
    return [interp_alt(alt,ne,h) for h in PROFILE_ALTITUDES]


def interp_alt(alts, values, h):
    a=find_bracket(alts,h)
    if not a:return None
    i,j,t=a
    if values[i] is None or values[j] is None:return None
    return (1-t)*values[i]+t*values[j]


def integral_tec(ne, alts=PROFILE_ALTITUDES):
    if len(ne)!=len(alts): raise ValueError('IRI profile length mismatch')
    return sum((b-a)*1000*(u+v)/2 for a,b,u,v in zip(alts,alts[1:],ne,ne[1:]))/1e16


def f2_peak(ne, alts=PROFILE_ALTITUDES):
    eligible=[(h,v) for h,v in zip(alts,ne) if 180<=h<=600 and finite(v) is not None]
    if not eligible:return None
    h,n=max(eligible,key=lambda p:p[1])
    if n<=0:return None
    return {'nmf2_m3':n,'hmf2_km':h,'fof2_mhz':8.98*math.sqrt(n)/1e6}


def build_anchors(times, sites, provider, hours):
    gap=int(hours*2)
    if not 1<=gap<=96:raise ValueError('anchor_hours outside 0.5..48h')
    indexes=list(range(0,len(times),gap))
    if indexes[-1]!=len(times)-1:indexes.append(len(times)-1)
    anchors={};failures=[]
    for site_index,(lat,lon) in enumerate(sites):
        pairs={}
        for index in indexes:
            try:
                ne=profile_iri(provider,times[index],lat,lon)
                if any(v is None for v in ne): raise ValueError('Incomplete IRI vertical coverage')
                pairs[index]=ne
            except Exception as e:
                failures.append(f'IRI site {site_index}, anchor {index}: {str(e)[:100]}')
        if len(pairs)==len(indexes):anchors[site_index]=pairs
    return indexes,anchors,failures


def interpolate_anchors(frame_index, indexes, pairs):
    if frame_index in pairs:return pairs[frame_index]
    lo=max(i for i in indexes if i<frame_index)
    hi=min(i for i in indexes if i>frame_index)
    t=(frame_index-lo)/(hi-lo)
    return [max(0, (1-t)*a+t*b) for a,b in zip(pairs[lo],pairs[hi])]


def scenario(ne, tec):
    """Reject arbitrary VTEC/partial TEC mismatch, maintain hmF2 from IRI."""
    peak=f2_peak(ne)
    if peak is None:return None,'IRI_PEAK_UNAVAILABLE',None
    partial=integral_tec(ne)
    if tec is None or partial<=0:return None,'VTEC_MISSING',partial
    if ne[-1] / max(ne) > 0.1:return None,'TOPSIDE_TRUNCATION',partial
    f=tec/partial
    if not 0.5<=f<=2.0:return None,'VTEC_PARTIAL_TEC_MISMATCH',partial
    return f,'SCENARIO_AVAILABLE',partial


def status_payload(now, status, reason, index=None):
    return {'schema':SCHEMA,'metadata':{'generated_at':iso(now),
             'issued_at':iso(now),'status':status,
             'source':'IRI2020 future-time anchors and SWIFT-TEC 30-minute forecast',
             'is_validated_forecast':False, 'is_observed_3d_density':False,
             'scenario_type':'BOUNDED_UNIFORM_PROFILE_SCALING',
             'warning':reason},'status':status,
             'altitudes_km':DISPLAY_ALTITUDES,
             'sites':[],'frames':[],'model_failures':[]}


def build(animation_dir, ionosphere, output, *, now=None, iri_provider=None,
          max_sites=16, anchor_hours=12):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('Run time must have timezone')
    base=Path(animation_dir)
    idx=json.loads((base/'index.json').read_text(encoding='utf-8'))
    if idx.get('schema')!='swift-ion-vtec-animation-v1':raise ValueError('Unexpected VTEC animation schema')
    if idx['metadata'].get('is_forecast') is not True or idx['metadata'].get('units')!='TECU':
        raise ValueError('TEC forecast units/role mismatch')
    if idx['metadata'].get('time_step_minutes')!=30 or idx['metadata'].get('value_scale')!=10:
        raise ValueError('Expected exact 30min VTEC / 0.1 TECU stored units')
    ts=[utc(t) for t in idx['time_utc']]
    if len(ts)<2 or any(abs((b-a).total_seconds()-1800)>1 for a,b in zip(ts,ts[1:])):
        raise ValueError('Animation is not a continuous 30-minute series')
    lats=[float(x) for x in idx['latitudes']]
    lons=[float(x) for x in idx['longitudes']]
    if any(b<=a for a,b in zip(lats,lats[1:])) or any(b<=a for a,b in zip(lons,lons[1:])):
        raise ValueError('TEC grid axes are not sorted')
    ion=json.loads(Path(ionosphere).read_text(encoding='utf-8'))
    if ion.get('metadata',{}).get('is_forecast') is not False:
        raise ValueError('IRI source is not labeled climatology')
    locs=locations(ion,max_sites=max_sites)
    if iri_provider is None:
        try:
            from iri2020 import IRI
            from build_ionosphere import extract_iri_profile
            def iri_provider(t,lat,lon):
                return extract_iri_profile(IRI(t,[100,2000,25],lat,lon))
        except Exception as e:
            payload=status_payload(now,'IRI_UNAVAILABLE','IRI model could not be imported: '+str(e)[:150])
            write(output,payload)
            return payload
    anchor_indices,anchors,failures=build_anchors(ts,locs,iri_provider,anchor_hours)
    if len(anchors)<4:
        payload=status_payload(now,'IRI_UNAVAILABLE',f'Only {len(anchors)} complete IRI anchor sites')
        payload['model_failures']=failures[:12]
        write(output,payload)
        return payload
    site_indices=sorted(anchors)
    forecast_cells=[]
    required_frame=0
    for c in idx['chunks']:
        name=c['file']
        if not isinstance(name,str) or not name.startswith('frames_') or '/' in name or '\\' in name:
            raise ValueError('Unsafe animation chunk path')
        obj=json.loads((base/name).read_text(encoding='utf-8'))
        if obj.get('start')!=required_frame or len(obj['values'])!=c['count']:
            raise ValueError('Animation chunk/frame order mismatch')
        for arr in obj['values']:
            if len(arr)!=len(lats)*len(lons):raise ValueError('Animation frame grid mismatch')
            forecast_cells.append(arr)
        required_frame+=c['count']
    if len(forecast_cells)!=len(ts):raise ValueError('Animation time/frames mismatch')
    result=[];scenario_pairs=0
    for t_index,t in enumerate(ts):
        cells=[]
        for idx_site in site_indices:
            lat,lon=locs[idx_site]
            ne=interpolate_anchors(t_index,anchor_indices,anchors[idx_site]);pk=f2_peak(ne)
            if pk is None:continue
            vtec=bilinear_vtec(forecast_cells[t_index],lats,lons,lat,lon)
            factor,sc_status,partial=scenario(ne,vtec)
            disp=[interp_alt(PROFILE_ALTITUDES,ne,h) for h in DISPLAY_ALTITUDES]
            base_log=[round(math.log10(max(1,n)),4) if n is not None else None for n in disp]
            scen_log=[round(math.log10(max(1,n*factor)),4) if n is not None else None for n in disp] if factor is not None else [None]*len(disp)
            if factor is not None:scenario_pairs+=1
            cells.append({'lat':lat,'lon':lon,'method':'IRI_FUTURE_ANCHOR_TEMPORAL_INTERPOLATION',
                'ne_log10_m3':base_log,'iri_ne_log10_m3':base_log,'tec_ne_log10_m3':scen_log,
                'fof2_iri_mhz':round(pk['fof2_mhz'],3),'fof2_tec_mhz':round(pk['fof2_mhz']*math.sqrt(factor),3) if factor else None,
                'hmf2_iri_km':round(pk['hmf2_km'],1),'hmf2_tec_km':round(pk['hmf2_km'],1) if factor else None,
                'vtec_forecast_tecu':round(vtec,3) if vtec is not None else None,
                'iri_partial_tec_100_2000_tecu':round(partial,3) if partial is not None else None,
                'factor':round(factor,5) if factor is not None else None,
                'scenario_status':sc_status})
        result.append({'valid_at':iso(t),'is_prospective':t>now,
            'sites':cells,'eligible_tec_scaling_sites':sum(c['factor'] is not None for c in cells)})
    status='AVAILABLE' if result and sum(f['is_prospective'] for f in result)>0 else 'HISTORICAL_REPLAY_ONLY'
    payload={'schema':SCHEMA,'status':status,'altitudes_km':DISPLAY_ALTITUDES,
         'metadata':{'generated_at':iso(now),'issued_at':iso(now),
          'tec_generated_at':idx['metadata'].get('generated_at'),
          'source_stage':idx['metadata'].get('source_stage','unverified'),
          'source':'SWIFT-TEC 30-minute VTEC + IRI2020 future-time profiles',
          'is_validated_forecast':False,'is_observed_3d_density':False,
          'has_prospective_frames':any(f['is_prospective'] for f in result),
          'scenario_type':'BOUNDED_UNIFORM_PROFILE_SCALING',
          'iri_anchor_hours':anchor_hours,'iri_profiles_computed':len(anchors)*len(anchor_indices),
          'iri_valid_sites':len(anchors),'tec_scenario_site_frames':scenario_pairs,
          'time_step_minutes':30,'htop_partial_tec_km':2000,
          'fof2_definition':'foF2 = 8.98 sqrt(NmF2[m-3]) / 1e6 MHz',
          'hmf2_is_iri_only':True,'is_forecast_skill':False,
          'time_interpolation':'IRI electron-density profiles linearly interpolated between future 12-hour (configurable) IRI anchor calculations; no independent model dynamics',
          'warnings':['EXPERIMENTAL: TEC does NOT uniquely determine vertical electron density or hmF2.',
            'SWIFT-TEC full VTEC vs IRI 100-2000km partial TEC have different column definitions.',
            'TEC-linked density and foF2 scenarios require bounded factor [0.5,2.0] and nontruncated IRI topside.',
            'hmF2 is IRI baseline only, unchanged by uniform TEC scaling.',
            'No prospective skill estimate until independently validated by later ionosonde observations.',
            'Frames at or before issuance are retrospective model replay, not prospective forecasts.']},
         'sites':[{'lat':locs[i][0],'lon':locs[i][1]} for i in site_indices],
         'frames':result,'model_failures':failures[:12]}
    write(output,payload)
    print('SWIFT-ION 30-min model scenario:',status,'frames',len(result),'iri_sites',len(anchors),
          'iri_calls',len(anchors)*len(anchor_indices),'tec_scenario_site_frames',scenario_pairs,flush=True)
    return payload


def write(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8')
    tmp.replace(p)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--animation',type=Path,default=ROOT/'docs/animation')
    ap.add_argument('--ionosphere',type=Path,default=ROOT/'docs/ionosphere.json')
    ap.add_argument('--output',type=Path,default=ROOT/'docs/ion_forecast.json')
    ap.add_argument('--max-sites',type=int,default=16)
    ap.add_argument('--anchor-hours',type=int,default=12)
    a=ap.parse_args()
    try:build(a.animation,a.ionosphere,a.output,max_sites=a.max_sites,anchor_hours=a.anchor_hours)
    except (OSError,ValueError,KeyError,TypeError,ImportError) as exc:
        # If the OPTIONAL model cannot run, preserve every established operation.
        print('WARNING: experimental ionosphere forecast unavailable:',str(exc),file=sys.stderr)
        write(a.output,status_payload(datetime.now(timezone.utc),'MODEL_UNAVAILABLE',str(exc)[:180]))


if __name__=='__main__':main()
