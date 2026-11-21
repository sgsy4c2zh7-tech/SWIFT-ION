"""IRI-2020 adapter and SWIFT-TEC VTEC-constrained profiles.

Requires optional `iri2020` package and its compiled IRI backend. No synthetic fallback.
Input: docs/swift_tec_vtec.json, output: docs/ionosphere.json.
"""
import argparse
import json
import math
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALT = list(range(100, 601, 20))  # IRI bottomside/topside, not D layer

def integrate(alt, ne):
    return sum((b-a)*1000*(x+y)/2 for a,b,x,y in zip(alt,alt[1:],ne,ne[1:]))/1e16

def diagnose(alt, ne):
    eligible = [(h,n) for h,n in zip(alt,ne) if 180 <= h <= 600]
    hm, nm = max(eligible, key=lambda x:x[1])
    # plasma frequency f_p [Hz] = 8.98 sqrt(Ne [m^-3]); convert to MHz
    return {'nmf2_m3':round(nm,2),'hmf2_km':hm,'fof2_mhz':round(8.98*math.sqrt(nm)/1e6,3),
            'peak_at_boundary':hm in (180,600)}

def extract_iri_profile(dataset):
    """Read documented iri2020 xarray dataset 'ne' and 'alt_km' coordinate.
    IRI package output conventions are checked, not guessed or silently rescaled.
    """
    if 'ne' not in dataset:
        raise ValueError('IRI result lacks ne variable')
    v = dataset['ne'].squeeze()
    if v.ndim != 1:
        raise ValueError('Expected single-location 1D IRI ne profile')
    dims = v.dims
    if len(dims) != 1 or dims[0] not in ('alt_km','altitude','alt'):
        raise ValueError(f'Unexpected IRI altitude dimension {dims}; inspect upstream package')
    alt = [float(x) for x in dataset[dims[0]].values]
    ne = [float(x) for x in v.values]
    if len(alt) < 2 or any(not math.isfinite(n) or n<0 for n in ne):
        raise ValueError('IRI electron density invalid')
    if max(ne) < 1e7 or max(ne)>1e14:
        raise ValueError('IRI ne units appear inconsistent with m^-3')
    return alt, ne

def build(input_path, output_path, max_cells, max_frames):
    try:
        from iri2020 import IRI
    except ImportError as exc:
        raise RuntimeError('Install and validate iri2020 before enabling IRI integration') from exc
    raw=json.loads(input_path.read_text(encoding='utf-8'))
    if raw.get('metadata',{}).get('is_forecast') is not True:
        raise ValueError('Input is not labeled as a forecast')
    out=[]
    for frame in raw['frames'][:max_frames]:
        t=datetime.fromisoformat(frame['valid_at'].replace('Z','+00:00'))
        cells=[]
        for c in frame['cells'][:max_cells]:
            target=float(c['vtec_tecu'])
            if not math.isfinite(target) or not 0<=target<=200:
                continue
            ds=IRI(t,[100,600,20],float(c['lat']),float(c['lon']))
            alt,ne=extract_iri_profile(ds)
            partial=integrate(alt,ne)
            if partial<=0: continue
            # IMPORTANT: this is a 100-600km PARTIAL TEC shape constraint.
            # VTEC includes plasma above 600km; matching it exactly would be invalid.
            diag=diagnose(alt,ne)
            cells.append({'lat':c['lat'],'lon':c['lon'],'vtec_swifttec_tecu':target,
                'iri_partial_tec_100_600_tecu':round(partial,3),
                'iri':diag,'profile':{'alt_km':alt,'ne_m3':ne}})
        out.append({'valid_at':frame['valid_at'],'cells':cells})
    payload={'metadata':{'source':'IRI-2020 via iri2020; SWIFT-TEC VTEC used for comparison only',
        'kind':'IRI_MODEL_ESTIMATE','is_forecast':False,'is_observation':False,
        'generated_at':datetime.now().astimezone().isoformat(),
        'warning':'IRI climatological estimates, NOT TEC-assimilated layer forecasts. 100-600km partial TEC is not full VTEC. D layer excluded.',
        'iri_altitude_km':[100,600,20], 'swiftec_source_stage':raw['metadata'].get('source_stage','unknown')},'frames':out}
    output_path.parent.mkdir(parents=True,exist_ok=True)
    output_path.write_text(json.dumps(payload,separators=(',',':')),encoding='utf-8')
    print('Wrote IRI estimates:',len(out),'frames',sum(len(f['cells']) for f in out),'cells')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,default=ROOT/'docs/swift_tec_vtec.json')
    p.add_argument('--output',type=Path,default=ROOT/'docs/ionosphere.json')
    p.add_argument('--max-cells',type=int,default=24)
    p.add_argument('--max-frames',type=int,default=1)
    a=p.parse_args()
    build(a.input,a.output,a.max_cells,a.max_frames)
