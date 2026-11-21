"""Build SWIFT-ION v0.8 scientific diagnostics and retrospective GloTEC comparison.

Important distinctions:
- IRI 100-2000 km partial TEC vs SWIFT-TEC VTEC is a model discrepancy,
  NOT forecast skill (different column definitions, both models).
- Retrospective NOAA GloTEC archive is a model/assimilation product, NOT
  independent truth. Compare only a prospective forecast (issued < valid UTC)
  after the matching reference timestamp has arrived.
- No result is fabricated on missing/stale reference data.
Python standard library only. Upstream SWIFT-TEC archive is read-only.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]


def utc(text):
    value=datetime.fromisoformat(str(text).replace('Z','+00:00'))
    if value.tzinfo is None:
        raise ValueError('Timezone is required: '+str(text))
    return value.astimezone(timezone.utc)


def median(vals):
    return round(statistics.median(vals),3) if vals else None


def numbers(vals):
    return [float(v) for v in vals if isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v)]


def stats(pred,ref):
    if len(pred)!=len(ref) or not pred: raise ValueError('Equal nonempty pairs required')
    differences=[a-b for a,b in zip(pred,ref)]
    return {'sample_count':len(differences),
        'mae_tecu':round(statistics.mean(abs(v) for v in differences),3),
        'rmse_tecu':round(math.sqrt(statistics.mean(v*v for v in differences)),3),
        'bias_tecu':round(statistics.mean(differences),3)}


def model_discrepancy(frame):
    matches=[]
    for c in frame.get('cells',[]):
        try:
            a=float(c['vtec_swifttec_tecu'])
            b=float(c['iri_partial_tec_100_2000_tecu'])
            if all(math.isfinite(x) for x in (a,b)) and a>=0 and b>=0:
                matches.append((a,b))
        except (TypeError,ValueError,KeyError): pass
    if not matches:
        return {'status':'unavailable','reason':'No valid IRI/SWIFT-TEC paired cells'}
    delta=[a-b for a,b in matches]
    return {'status':'available','paired_sites':len(matches),
        'median_swifttec_vtec_tecu':median([a for a,b in matches]),
        'median_iri_partial_100_2000_tecu':median([b for a,b in matches]),
        'median_signed_difference_tecu':median(delta),
        'median_absolute_difference_tecu':median([abs(x) for x in delta]),
        'meaning':'MODEL_DISCREPANCY_NOT_ACCURACY; different vertical coverage'}


def quality_summary(frame):
    cells=frame.get('cells',[])
    mapped=frame.get('map_cells',[])
    dist=numbers([x.get('nearest_iri_km') for x in mapped])
    valid_scenarios=sum(1 for c in cells if c.get('tec_scenario') is not None)
    counts={}
    for x in mapped:
        key=x.get('method','UNKNOWN');counts[key]=counts.get(key,0)+1
    return {'iri_computations':len(cells),'display_cells':len(mapped),
        'methods':counts,
        'scenario_eligible_sites':valid_scenarios,
        'scenario_fraction':round(valid_scenarios/len(cells),4) if cells else None,
        'interpolation_distance_km_median':median(dist),
        'interpolation_distance_km_max':round(max(dist),1) if dist else None,
        'interpolated_more_than_1500km':sum(d>1500 for d in dist),
        'boundary_peaks':sum(bool(c.get('iri',{}).get('peak_at_boundary')) for c in cells)}


def norm_lon(lon):
    return round((float(lon)+180)%360-180,4)


def archive_cells(frame):
    """Normalize NOAA archive grid: lat_arr, lon_arr, grid (seen in upstream JS reader)."""
    lats=frame['lat_arr'];lons=frame['lon_arr'];grid=frame['grid']
    if not lats or not lons or len(grid)!=len(lats): raise ValueError('Invalid NOAA archive grid')
    values={}
    for i,lat in enumerate(lats):
        if len(grid[i])!=len(lons):raise ValueError('Wrong NOAA grid shape')
        for j,lon in enumerate(lons):
            try: v=float(grid[i][j])
            except (TypeError,ValueError):continue
            if math.isfinite(v) and 0<=v<=200:
                values[(round(float(lat),4),norm_lon(lon))]=v
    return values


def retrospective(forecast, archive_dir, now):
    """Compares only exact lat/lon/time matches of prospectively issued frames.

    Pending when any source evidence is missing. No spatial interpolation, no
    matching nearest timestamp, no use of future GloTEC files.
    """
    result={'source':'NOAA GloTEC-derived SWIFT-TEC public archive (model-based reference)',
        'role':'RETROSPECTIVE_REFERENCE_NOT_INDEPENDENT_GROUND_TRUTH',
        'comparison':'Forecast SWIFT-TEC VTEC minus later GloTEC VTEC [TECU]',
        'frames':[]}
    issued_raw=forecast.get('metadata',{}).get('generated_at')
    if not issued_raw:
        result['status']='unavailable';result['reason']='Forecast issue time not recorded';return result
    issued=utc(issued_raw)
    idx_path=Path(archive_dir)/'index.json'
    if not idx_path.exists():
        result['status']='unavailable';result['reason']='NOAA archive index not present';return result
    idx=json.loads(idx_path.read_text(encoding='utf-8'))
    idx_updated=utc(idx['updated_utc'])
    indexes={utc(x['time_utc']):x['file'] for x in idx.get('frames',[]) if x.get('time_utc') and x.get('file')}
    base=Path(archive_dir).resolve()
    outcomes=[]
    for f in forecast.get('frames',[]):
        valid=utc(f['valid_at'])
        record={'valid_at':f['valid_at'],'forecast_issued_at':issued_raw}
        if valid<=issued:
            record.update(status='ineligible',reason='Target time was not after forecast issue time')
        elif valid>now:
            record.update(status='pending',reason='Forecast target is in the future')
        elif valid>idx_updated:
            record.update(status='pending',reason='Reference archive has not reached target time')
        elif valid not in indexes:
            record.update(status='unavailable',reason='No exact-time NOAA archive frame')
        else:
            path=(base/indexes[valid]).resolve()
            if not path.is_relative_to(base):
                record.update(status='unavailable',reason='Unsafe archive reference path')
            elif not path.is_file():
                record.update(status='unavailable',reason='Archive frame not available in checkout')
            else:
                try:
                    if path.stat().st_size>10_000_000: raise ValueError('Reference archive exceeds 10 MB compressed')
                    if path.suffix=='.gz':
                        with gzip.open(path,'rt',encoding='utf-8') as fh: observed=json.load(fh)
                    else: observed=json.loads(path.read_text(encoding='utf-8'))
                    if utc(observed.get('time_utc',f['valid_at']))!=valid:
                        raise ValueError('Reference timestamp mismatch')
                    values=archive_cells(observed)
                    predicted=[];reference=[]
                    for c in f.get('cells',[]):
                        key=(round(float(c['lat']),4),norm_lon(c['lon']))
                        try: v=float(c['vtec_tecu'])
                        except (TypeError,KeyError,ValueError): continue
                        if key in values and math.isfinite(v) and 0<=v<=200:
                            predicted.append(v);reference.append(values[key])
                    # explicitly require substantial exact-grid support; no made-up spatial interpolation
                    if len(predicted)<30:
                        record.update(status='insufficient',reason='Fewer than 30 exact coordinate matches',matched_cells=len(predicted),forecast_cells=len(f.get('cells',[])))
                    else:
                        record.update(status='evaluated',matched_cells=len(predicted),forecast_cells=len(f.get('cells',[])),**stats(predicted,reference))
                except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError,EOFError) as ex:
                    record.update(status='unavailable',reason=f'Could not read reference frame: {str(ex)[:150]}')
        outcomes.append(record)
    result['frames']=outcomes
    result['evaluated_frames']=sum(x['status']=='evaluated' for x in outcomes)
    result['status']='available' if result['evaluated_frames'] else 'pending_or_unavailable'
    result['archive_updated_at']=idx['updated_utc']
    return result


def build(ion_path, tec_path, archive_dir, out_path, now=None):
    now=now or datetime.now(timezone.utc)
    ion=json.loads(Path(ion_path).read_text(encoding='utf-8'))
    tec=json.loads(Path(tec_path).read_text(encoding='utf-8'))
    if ion.get('metadata',{}).get('is_forecast') is not False:
        raise ValueError('IRI should be explicitly marked as climatology/non-forecast')
    if tec.get('metadata',{}).get('is_forecast') is not True:
        raise ValueError('Source TEC must be a forecast')
    if not ion.get('frames'):raise ValueError('No IRI frames')
    selected=[]
    for frame in ion['frames']:
        selected.append({'valid_at':frame['valid_at'],
                         'quality':quality_summary(frame),
                         'model_discrepancy':model_discrepancy(frame)})
    report={'metadata':{
        'schema_version':'swift-ion-quality-v1','generated_at':now.isoformat(),
        'iri_source':ion['metadata'].get('iri_model','unspecified'),
        'tec_source':tec['metadata'].get('source','unspecified'),
        'tec_correction_stage':tec['metadata'].get('source_stage','unverified'),
        'tec_generated_at':tec['metadata'].get('generated_at'),
        'iri_generated_at':ion['metadata'].get('generated_at'),
        'warning':'IRI is climatology; IRI partial 100-2000 km TEC differs in definition from full VTEC. NOAA GloTEC is not independent ground truth. SWIFT-TEC ML correction stage not verified.'},
        'iri_model_diagnostics':selected,
        'retrospective_noaa_glotec':retrospective(tec,archive_dir,now)}
    p=Path(out_path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(report,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8');tmp.replace(p)
    print(f'Quality report wrote {p}: {len(selected)} IRI frames; {report["retrospective_noaa_glotec"].get("evaluated_frames",0)} mature NOAA matches')
    return report

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--ionosphere',type=Path,default=ROOT/'docs/ionosphere.json')
    a.add_argument('--forecast',type=Path,default=ROOT/'docs/swift_tec_vtec.json')
    a.add_argument('--archive',type=Path,default=ROOT/'_upstream_swifttec/docs/data/tec')
    a.add_argument('--out',type=Path,default=ROOT/'docs/quality.json')
    args=a.parse_args();build(args.ionosphere,args.forecast,args.archive,args.out)
