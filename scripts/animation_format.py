"""30-minute tiled VTEC forecast web-format; no interpolation or synthetic fill.
Store row-major lat ascending, lon in [-180,180), TECU quantized to 0.1.
Upstream: SWIFT-TEC's full native grid/time frames, read-only calculation.
"""
from __future__ import annotations
import json, math
from datetime import datetime
from pathlib import Path

SCALE=10

def create_animation(animation_dir, time_strings, latitudes, longitudes, flattened_frames,
                     *, generated_at, source_stage='upstream runForecast; ML stage not verified', chunk_size=12):
    if not time_strings or not latitudes or not longitudes:
        raise ValueError('Missing time or grid axes')
    if not 1 <= chunk_size <= 48:
        raise ValueError('Chunk size outside expected range')
    ny,nx=len(latitudes),len(longitudes)
    if ny<2 or nx<2:
        raise ValueError('Grid must be at least 2x2')
    if any(not math.isfinite(float(x)) for x in latitudes+longitudes):
        raise ValueError('Grid axes contain nonfinite value')
    if any(b<=a for a,b in zip(latitudes,latitudes[1:])) or any(b<=a for a,b in zip(longitudes,longitudes[1:])):
        raise ValueError('Grid axes must ascend')
    ts=[datetime.fromisoformat(t.replace('Z','+00:00')) for t in time_strings]
    if any(t.tzinfo is None for t in ts):
        raise ValueError('Timezone required')
    if any(abs((b-a).total_seconds()-1800)>1 for a,b in zip(ts,ts[1:])):
        raise ValueError('SWIFT-TEC frame spacing is not 30 minutes')
    if len(flattened_frames)!=len(ts):
        raise ValueError('Frame/time count mismatch')
    for i,row in enumerate(flattened_frames):
        if len(row)!=ny*nx:
            raise ValueError(f'Frame {i} has {len(row)} values, expected {ny*nx}')
        if any(v is not None and (not isinstance(v,int) or not 0<=v<=10000) for v in row):
            raise ValueError(f'Frame {i} has nonquantized / invalid VTEC')
        if sum(v is not None for v in row)<0.8*ny*nx:
            raise ValueError(f'Frame {i} has insufficient valid cells')
    target=Path(animation_dir);target.mkdir(parents=True,exist_ok=True)
    # Pages builds happen on fresh checkout: remove only files owned by this writer.
    for old in target.glob('frames_*.json'):
        old.unlink()
    chunks=[]
    for start in range(0,len(ts),chunk_size):
        part=flattened_frames[start:start+chunk_size]
        filename=f'frames_{start//chunk_size:03d}.json'
        (target/filename).write_text(json.dumps({'start':start,'values':part},separators=(',',':'),allow_nan=False),encoding='utf-8')
        chunks.append({'file':filename,'start':start,'count':len(part)})
    idx={'schema':'swift-ion-vtec-animation-v1',
         'metadata':{'source':'SWIFT-TEC browser runForecast read-only',
                     'source_stage':source_stage,'generated_at':generated_at,
                     'is_forecast':True,'is_observation':False,
                     'sampled_for_animation':False,'quality':'unvalidated forecast; GNSS effects are simplified ionospheric estimates',
                     'units':'TECU','vertical_column':'VTEC; not slant TEC; not position error',
                     'time_step_minutes':30,'value_scale':SCALE,'null_is_missing':True},
         'latitudes':latitudes,'longitudes':longitudes,'time_utc':time_strings,
         'grid':{'nlat':ny,'nlon':nx,'order':'latitude-major','coordinate_bounds':'cell_centers'},
         'chunks':chunks}
    (target/'index.json').write_text(json.dumps(idx,separators=(',',':'),allow_nan=False),encoding='utf-8')
    return idx


def check_animation(directory, expected_min_frames=48):
    base=Path(directory)
    idx=json.loads((base/'index.json').read_text(encoding='utf-8'))
    if idx.get('schema')!='swift-ion-vtec-animation-v1':
        raise ValueError('Bad animation schema')
    if idx['metadata'].get('time_step_minutes') != 30:
        raise ValueError('Wrong temporal resolution')
    n=len(idx['time_utc'])
    if n<expected_min_frames:
        raise ValueError('Insufficient animation duration')
    ny,nx=idx['grid']['nlat'],idx['grid']['nlon']
    if ny*nx!=len(idx['latitudes'])*len(idx['longitudes']):
        raise ValueError('Grid dimension mismatch')
    ts=[datetime.fromisoformat(t.replace('Z','+00:00')) for t in idx['time_utc']]
    if any(abs((b-a).total_seconds()-1800)>1 for a,b in zip(ts,ts[1:])):
        raise ValueError('Bad frame timestamps')
    next_start=0
    for c in idx['chunks']:
        if c['start']!=next_start or not c['file'].startswith('frames_') or '/' in c['file']:
            raise ValueError('Missing, unordered or unsafe chunk path')
        payload=json.loads((base/c['file']).read_text(encoding='utf-8'))
        if payload['start']!=next_start or len(payload['values'])!=c['count']:
            raise ValueError('Chunk metadata mismatch')
        for frame in payload['values']:
            if len(frame)!=ny*nx:
                raise ValueError('Frame size mismatch')
            if any(v is not None and (not isinstance(v,int) or v<0 or v>10000) for v in frame):
                raise ValueError('Invalid VTEC frame values')
        next_start+=c['count']
    if next_start!=n:
        raise ValueError('Not all frames have chunks')
    return {'frames':n,'grid_cells':nx*ny,'chunks':len(idx['chunks']),
            'start':idx['time_utc'][0],'end':idx['time_utc'][-1]}
