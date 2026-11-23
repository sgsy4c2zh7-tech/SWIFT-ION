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
from fof2_ml import stage_predict, SCHEMA as CALIBRATION_SCHEMA
from build_fof2_drivers import drivers_at

ROOT = Path(__file__).resolve().parents[1]
PROFILE_ALTITUDES = list(range(100, 2001, 25))
DISPLAY_ALTITUDES = [100,150,200,250,300,350,400,500,600,800,1000]
# Public geographic research lattice. Japan sites are preferentially sampled at
# 6-hour IRI anchor times; global sites can use a coarser cadence to bound runtime.
JAPAN_SITES = [(43.06,141.35),(38.27,140.87),(35.68,139.76),
               (35.18,136.91),(34.70,135.50),(34.40,132.46),
               (33.59,130.40),(31.60,130.56),(26.21,127.68)]
JAPAN_BOUNDS = (23.0, 47.0, 121.0, 152.0)
SITE_LAYOUT = 'JAPAN_MAXMIN_PLUS_GLOBAL_EQUAL_AREA_FIBONACCI_V1' 
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


def in_japan(lat, lon):
    south, north, west, east = JAPAN_BOUNDS
    return south <= lat <= north and west <= lon <= east


def fibonacci_sites(n):
    """Near-equal-area deterministic sphere candidates. No pseudo-observation."""
    if n < 1:
        return []
    golden = math.pi * (3 - math.sqrt(5))
    out = []
    for i in range(n):
        z = 1 - 2 * (i + .5) / n
        lat = math.degrees(math.asin(max(-1, min(1, z))))
        lon = (math.degrees(i * golden) + 180) % 360 - 180
        out.append((round(lat, 5), round(lon, 5)))
    return out


def farthest_fill(start, candidates, target):
    """Incrementally maximize great-circle spacing; O(candidates * new sites)."""
    chosen = list(start)
    existing = set(chosen)
    pending = [p for p in candidates if p not in existing]
    if not pending or len(chosen) >= target:
        return chosen[:target]
    if chosen:
        distance = [min(distance_km(p, q) for q in chosen) for p in pending]
    else:
        distance = [1e9] * len(pending)
    while len(chosen) < target and pending:
        best = max(range(len(pending)), key=lambda i: distance[i])
        candidate = pending.pop(best)
        distance.pop(best)
        if candidate in existing:
            continue
        chosen.append(candidate)
        existing.add(candidate)
        for i, p in enumerate(pending):
            distance[i] = min(distance[i], distance_km(p, candidate))
    return chosen


def locations(global_json, max_sites=120, japan_sites=40):
    """High-density Japan grid + equal-area global IRI sites.

    The global candidates are new IRI locations, never fake values interpolated
    from a previous IRI frame. Historical IRI cells are not treated as new runs.
    """
    if not 4 <= max_sites <= 180:
        raise ValueError('max-sites must be 4..180')
    if not 0 <= japan_sites <= max_sites:
        raise ValueError('japan-sites must be 0..max-sites')
    # Regular candidate lattice covering Japan's surroundings and adjacent seas.
    local = [(round(23.5 + 3*i, 3), round(121.5 + 3.75*j, 3))
             for i in range(8) for j in range(9) if 23 <= 23.5 + 3*i <= 47
             and 121 <= 121.5 + 3.75*j <= 152]
    starters = list(JAPAN_SITES[:min(japan_sites, len(JAPAN_SITES))])
    japan = farthest_fill(starters, local, japan_sites)
    # Equal-area globe with min-distance greedy coverage: near-uniform spacing
    # at high latitudes as well as in the tropics; avoid re-filling Japan.
    spherical = [p for p in fibonacci_sites(max(680, 5 * max_sites))
                 if not in_japan(*p)]
    return farthest_fill(japan, spherical, max_sites)


def _anchor_grid(nframes, hours):
    steps = round(hours * 2)
    if not (1 <= steps <= 96) or abs(steps - hours * 2) > 1e-8:
        raise ValueError('Anchor interval must be a multiple of 0.5h in [0.5,48]')
    indexes = list(range(0, nframes, steps))
    if indexes[-1] != nframes-1:
        indexes.append(nframes-1)
    return indexes

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


def build_anchors(times, sites, provider, hours, *, japan_site_count=None,
                  global_hours=None):
    """Calculate real IRI profiles on regional 6h / global 12h anchors.

    Retain only sites with a full anchor sequence; unavailable profiles are
    marked as missing, not substituted from other locations or dates.
    """
    japan_site_count = len(sites) if japan_site_count is None else japan_site_count
    global_hours = hours if global_hours is None else global_hours
    regional_idx = _anchor_grid(len(times), hours)
    global_idx = _anchor_grid(len(times), global_hours)
    anchors, failures = {}, []
    attempted = 0
    for site_index, (lat, lon) in enumerate(sites):
        indexes = regional_idx if site_index < japan_site_count else global_idx
        pairs = {}
        for idx in indexes:
            attempted += 1
            try:
                ne = profile_iri(provider, times[idx], lat, lon)
                if any(v is None for v in ne):
                    raise ValueError('Incomplete IRI vertical coverage')
                pairs[idx] = ne
            except Exception as exc:
                failures.append(f'IRI site {site_index}, anchor {idx}: {str(exc)[:100]}')
        if len(pairs) == len(indexes):
            anchors[site_index] = {'indexes': indexes, 'pairs': pairs}
    return anchors, failures, attempted

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


def extended_scenario(ne, tec):
    """Quality-tagged, conservative continuation when strict ratio fails.

    STANDARD values exactly preserve the original bounded physics rule.
    EXTENDED is a low-confidence *sensitivity estimate* (not validated or a
    measured foF2). It is never used to certify a strict match or train ML.
    Cannot fabricate missing input VTEC or IRI F2 peak.
    """
    f, reason, partial = scenario(ne, tec)
    if f is not None:
        return f, 'SCENARIO_AVAILABLE', partial, 'STANDARD'
    if reason not in ('VTEC_PARTIAL_TEC_MISMATCH', 'TOPSIDE_TRUNCATION'):
        return None, reason, partial, 'MISSING'
    if finite(tec, 0.001, 1000) is None or not partial or partial <= 0:
        return None, 'VTEC_MISSING', partial, 'MISSING'
    ratio = float(tec)/partial
    if not math.isfinite(ratio) or ratio <= 0:
        return None, 'VTEC_MISSING', partial, 'MISSING'
    # C1-continuous low-gain saturation beyond the strict [.5, 2] window.
    # Lower branch approaches .35, upper branch approaches 2.5, rather than
    # deriving extreme foF2 from mismatched (VTEC vs IRI partial) columns.
    if ratio < 0.5:
        factor = .35 + .15 * math.exp(-(0.5-ratio)/.15)
        status = 'EXTENDED_RATIO_LOW'
    elif ratio > 2:
        factor = 2 + .5 * (1-math.exp(-(ratio-2)/.5))
        status = 'EXTENDED_RATIO_HIGH'
    else:
        factor = ratio
        status = 'EXTENDED_TOPSIDE'
    if reason == 'TOPSIDE_TRUNCATION' and status != 'EXTENDED_TOPSIDE':
        status = 'EXTENDED_RATIO_TOPSIDE'
    return factor, status, partial, 'EXTENDED'


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
          max_sites=120, anchor_hours=6, japan_sites=40, global_anchor_hours=12,
          calibration=None, drivers=None):
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
    japan_sites=min(japan_sites,max_sites)
    locs=locations(ion,max_sites=max_sites,japan_sites=japan_sites)
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
    anchors,failures,attempted=build_anchors(ts,locs,iri_provider,anchor_hours,
                                      japan_site_count=min(japan_sites,len(locs)),
                                      global_hours=global_anchor_hours)
    minimum_valid=max(4,math.ceil(max_sites*.65)) if max_sites>=80 else 4
    if len(anchors)<minimum_valid:
        payload=status_payload(now,'IRI_UNAVAILABLE',f'Only {len(anchors)}/{max_sites} complete IRI anchor sites (required {minimum_valid})')
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
    # Calibration and drivers are strictly issue-time inputs. Failed or absent
    # inputs are neutral; do not invent measurements or use future labels.
    calibration_model = None
    driver_payload = None
    if calibration and Path(calibration).is_file():
        try:
            obj=json.loads(Path(calibration).read_text(encoding='utf-8'))
            if obj.get('schema')==CALIBRATION_SCHEMA and utc(obj['trained_at']) <= now:
                calibration_model=obj
        except (ValueError,KeyError,TypeError):pass
    if drivers and Path(drivers).is_file():
        try:
            obj=json.loads(Path(drivers).read_text(encoding='utf-8'))
            if obj.get('schema')=='swift-ion-fof2-driver-v1' and utc(obj['fetched_at']) <= now:
                driver_payload=obj
        except (ValueError,KeyError,TypeError):pass
    result=[];scenario_pairs=0
    stages={'PHYSICS':0,'EMPIRICAL':0,'AI':0,'UNAVAILABLE':0}
    quality_counts={'STANDARD':0,'EXTENDED':0,'MISSING':0}
    for t_index,t in enumerate(ts):
        cells=[]
        for idx_site in site_indices:
            lat,lon=locs[idx_site]
            entry=anchors[idx_site]
            ne=interpolate_anchors(t_index,entry["indexes"],entry["pairs"]);pk=f2_peak(ne)
            if pk is None:continue
            vtec=bilinear_vtec(forecast_cells[t_index],lats,lons,lat,lon)
            strict_factor,strict_status,_=scenario(ne,vtec)
            factor,sc_status,partial,quality=extended_scenario(ne,vtec)
            quality_counts[quality] += 1
            disp=[interp_alt(PROFILE_ALTITUDES,ne,h) for h in DISPLAY_ALTITUDES]
            base_log=[round(math.log10(max(1,n)),4) if n is not None else None for n in disp]
            scen_log=[round(math.log10(max(1,n*factor)),4) if n is not None else None for n in disp] if factor is not None else [None]*len(disp)
            if factor is not None:scenario_pairs+=1
            kp,f107=drivers_at(driver_payload,t,now) if driver_payload else (None,None)
            physics=pk['fof2_mhz']*math.sqrt(factor) if factor is not None else None
            # ML coefficients are calibrated on STANDARD pairs only; never
            # extrapolate their learned correction to EXTENDED quality sites.
            eligible_calibration=calibration_model if quality=='STANDARD' else None
            calibrated=stage_predict(physics,pk['fof2_mhz'],lat,lon,t,kp,f107,eligible_calibration)
            stages[calibrated['stage']]+=1
            cells.append({'lat':lat,'lon':lon,'method':'IRI_FUTURE_ANCHOR_TEMPORAL_INTERPOLATION',
                'ne_log10_m3':base_log,'iri_ne_log10_m3':base_log,'tec_ne_log10_m3':scen_log,
                'fof2_iri_mhz':round(pk['fof2_mhz'],3),
                'fof2_tec_mhz':calibrated['selected'],
                'fof2_strict_mhz':round(pk['fof2_mhz']*math.sqrt(strict_factor),3) if strict_factor is not None else None,
                'fof2_quality':quality,
                'fof2_raw_vtec_ratio':round(vtec/partial,5) if (partial and vtec is not None) else None,
                'fof2_strict_failure':strict_status if strict_factor is None else None,
                'fof2_physics_mhz':calibrated['physics'],
                'fof2_empirical_mhz':calibrated['empirical'],
                'fof2_ai_mhz':calibrated['ai'],
                'fof2_stage_used':calibrated['stage'],
                'kp_forecast':kp,'f107_available':f107,
                'kp_3day_confirmed':bool(kp is not None and driver_payload and driver_payload.get('kp_source_mode')=='SWIFTTEC_SAME_ISSUE_NOAA_3DAY'),
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
          'kp_issue_provenance':driver_payload.get('kp_source_mode','UNAVAILABLE') if isinstance(driver_payload,dict) else 'UNAVAILABLE',
          'source':'SWIFT-TEC 30-minute VTEC + IRI2020 future-time profiles',
          'is_validated_forecast':False,'is_observed_3d_density':False,
          'has_prospective_frames':any(f['is_prospective'] for f in result),
          'scenario_type':'BOUNDED_UNIFORM_PROFILE_SCALING',
          'iri_anchor_hours':anchor_hours,'iri_profiles_computed':sum(len(a['indexes']) for a in anchors.values()),
          'iri_profiles_attempted':attempted,
          'iri_japan_requested_sites':min(japan_sites,len(locs)),
          'iri_global_requested_sites':max(0,len(locs)-japan_sites),
          'iri_japan_valid_sites':sum(i<japan_sites for i in anchors),
          'iri_global_valid_sites':sum(i>=japan_sites for i in anchors),
          'iri_global_anchor_hours':global_anchor_hours,
          'iri_site_distribution':SITE_LAYOUT,
          'minimum_valid_sites_required':minimum_valid,
          'map_resolution_note':'Spatial interpolation does not increase physical IRI information.',
          'iri_valid_sites':len(anchors),'tec_scenario_site_frames':scenario_pairs,
          'fof2_calibration_schema':CALIBRATION_SCHEMA,
          'fof2_calibration_status':calibration_model.get('status') if calibration_model else 'PHYSICS_ONLY',
          'fof2_selected_stage_counts':stages,
          'fof2_quality_counts':quality_counts,
          'fof2_extended_is_validated':False,
          'fof2_extended_method':'Smooth bounded continuation [0.35,2.5] of raw SWIFT-TEC VTEC / IRI 100-2000 km partial TEC ratio; research sensitivity only',
          'f107_is_observed_persistence_not_forecast':True,
          'fof2_postprocessing_not_self_consistent_3d_density':True,
          'time_step_minutes':30,'htop_partial_tec_km':2000,
          'fof2_definition':'foF2 = 8.98 sqrt(NmF2[m-3]) / 1e6 MHz',
          'hmf2_is_iri_only':True,'is_forecast_skill':False,
          'time_interpolation':f'Japan: {anchor_hours}h IRI anchors; outside Japan: {global_anchor_hours}h IRI anchors. All 30-minute frames in between are time-interpolated, not model dynamics.',
          'warnings':['EXPERIMENTAL: TEC does NOT uniquely determine vertical electron density or hmF2.',
            'SWIFT-TEC full VTEC vs IRI 100-2000km partial TEC have different column definitions.',
            'TEC-linked density and foF2 scenarios require bounded factor [0.5,2.0] and nontruncated IRI topside.',
            'hmF2 is IRI baseline only, unchanged by uniform TEC scaling.',
            'Empirical and nonlinear ridge AI corrections are activated ONLY after chrono holdout improvement; may initially be inactive.',
            'foF2 statistical postprocessing does not modify Ne(h), hmF2 or a self-consistent ionosphere profile.',
            'Observed F10.7 is a persistence proxy, not a future forecast. Missing Kp/F10.7 features are neutral.',
            'EXTENDED foF2 is a LOW-CONFIDENCE provisional estimate when strict VTEC / IRI partial-TEC ratio or IRI topside criteria fail. Never treat smoother display as better accuracy.',
            'Empirical/AI corrections are intentionally disabled on EXTENDED model cells; only STANDARD prospective pairs are eligible for ML training.',
            'No prospective skill estimate until independently validated by later ionosonde observations.',
            'Frames at or before issuance are retrospective model replay, not prospective forecasts.']},
         'sites':[{'lat':locs[i][0],'lon':locs[i][1]} for i in site_indices],
         'frames':result,'model_failures':failures[:12]}
    write(output,payload)
    print('SWIFT-ION 30-min model scenario:',status,'frames',len(result),'iri_sites',len(anchors),
          'iri_calls',attempted,'japan_sites',min(japan_sites,len(locs)),'tec_scenario_site_frames',scenario_pairs,flush=True)
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
    ap.add_argument('--max-sites',type=int,default=120)
    ap.add_argument('--japan-sites',type=int,default=40)
    ap.add_argument('--anchor-hours',type=float,default=6)
    ap.add_argument('--global-anchor-hours',type=float,default=12)
    ap.add_argument('--calibration',type=Path,default=ROOT/'docs/fof2_calibration.json')
    ap.add_argument('--drivers',type=Path,default=ROOT/'docs/fof2_drivers.json')
    a=ap.parse_args()
    try:build(a.animation,a.ionosphere,a.output,max_sites=a.max_sites,anchor_hours=a.anchor_hours,
              japan_sites=min(a.japan_sites,a.max_sites),global_anchor_hours=a.global_anchor_hours,
              calibration=a.calibration,drivers=a.drivers)
    except (OSError,ValueError,KeyError,TypeError,ImportError) as exc:
        # If the OPTIONAL model cannot run, preserve every established operation.
        print('WARNING: experimental ionosphere forecast unavailable:',str(exc),file=sys.stderr)
        write(a.output,status_payload(datetime.now(timezone.utc),'MODEL_UNAVAILABLE',str(exc)[:180]))


if __name__=='__main__':main()
