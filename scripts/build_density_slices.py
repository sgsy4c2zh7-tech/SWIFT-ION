"""Export sparse IRI Ne(h) models as coarsely interpolated altitude slices.

NOT a real observed 3-D density field or an independently verified electron density forecast.
Longitude wrapping and great-circle spatial weights are handled explicitly.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HEIGHTS=(150,200,250,300,350,400,500,600,800,1000)

def profile_at(profile, h):
    al=profile['alt_km']; ne=profile['ne_m3']
    if len(al)!=len(ne) or len(al)<2 or h<al[0] or h>al[-1]:return None
    lo,hi=0,len(al)-1
    while lo<hi:
        m=(lo+hi)//2
        if al[m]<h:lo=m+1
        else:hi=m
    if al[lo]==h:return float(ne[lo])
    i=lo-1
    f=(h-al[i])/(al[lo]-al[i]);return float(ne[i])*(1-f)+float(ne[lo])*f

def distance(a,b):
    ar,ao=map(math.radians,a);br,bo=map(math.radians,b)
    c=math.sin(ar)*math.sin(br)+math.cos(ar)*math.cos(br)*math.cos(ao-bo)
    return 6371*math.acos(max(-1,min(1,c)))

def slice_frame(frame,heights=HEIGHTS,nearest_count=4):
    sources=[x for x in frame.get('cells',[]) if x.get('profile',{}).get('ne_m3')]
    targets=frame.get('map_cells',[])
    if not sources or not targets:raise ValueError('Missing IRI profile sites or map target cells')
    profiles=[[profile_at(s['profile'],h) for h in heights] for s in sources]
    values=[];max_ne=0
    for cell in targets:
        d=sorted(((distance((cell['lat'],cell['lon']),(s['lat'],s['lon'])),i) for i,s in enumerate(sources)),key=lambda x:x[0])[:nearest_count]
        if d[0][0]<1:
            series=profiles[d[0][1]]
        else:
            weights=[1/max(50.0,dis)**2 for dis,_ in d]
            series=[]
            for j in range(len(heights)):
                vals=[(w,profiles[i][j]) for w,(_,i) in zip(weights,d) if profiles[i][j] is not None]
                series.append(sum(w*v for w,v in vals)/sum(w for w,_ in vals) if vals else None)
        row=[]
        for ne in series:
            if ne is None or not math.isfinite(ne) or ne<0: row.append(None)
            else:
                max_ne=max(max_ne,ne)
                # logarithm gives compact dynamic range; 0 is meaningful here.
                row.append(round(math.log10(max(ne,1)),3))
        values.append(row)
    return {'valid_at':frame['valid_at'],'values_log10_ne_m3':values,
            'target_cells':len(targets),'iri_source_sites':len(sources),'max_ne_m3':max_ne}

def build(source,out):
    ion=json.loads(Path(source).read_text(encoding='utf-8'))
    if ion.get('metadata',{}).get('is_forecast') is not False:
        raise ValueError('IRI source must be model climatology, not a forecast')
    frames=ion.get('frames',[])
    if len(frames)<2:raise ValueError('At least two valid IRI model frames required')
    first=frames[0]['map_cells']
    locs=[[float(c['lat']),float(c['lon'])] for c in first]
    for f in frames:
        if [[float(c['lat']),float(c['lon'])] for c in f.get('map_cells',[])]!=locs:
            raise ValueError('IRI target-grid positions differ between frames')
    result={'schema':'swift-ion-iri-slices-v1',
            'metadata':{'source':'IRI-2020 climatology; spatial IDW of sparse IRI profiles',
                        'source_generated_at':ion['metadata'].get('generated_at'),
                        'model':'IRI-2020', 'is_forecast':False,'is_observation':False,
                        'height_units':'km','density_units':'log10(electrons/m^3)',
                        'method':'MODEL_PROFILE_ALTITUDE_LINEAR_AND_SPATIAL_IDW',
                        'warning':'IRI model sparse-space/time estimate; not measured 3-D electron density. Intermediate times must be labeled interpolation; not an independently validated forecast.'},
            'heights_km':list(HEIGHTS),'coordinates':locs,
            'frames':[slice_frame(f) for f in frames]}
    p=Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,separators=(',',':'),allow_nan=False),encoding='utf-8')
    print('IRI density slices:',len(result['frames']),'frames,',len(locs),'points,',len(HEIGHTS),'heights',flush=True)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,default=ROOT/'docs/ionosphere.json')
    ap.add_argument('--out',type=Path,default=ROOT/'docs/density_slices.json')
    args=ap.parse_args();build(args.source,args.out)
