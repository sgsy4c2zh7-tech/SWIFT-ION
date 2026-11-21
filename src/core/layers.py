"""Band diagnostics only: NOT validated ionosonde layer-peak estimates."""
from math import isfinite
BANDS_KM={'D':(60,90),'E':(90,150),'F1':(150,220),'F2':(220,600)}
def describe_layers(altitude_km,ne_m3):
    if len(altitude_km)!=len(ne_m3) or not altitude_km:
        raise ValueError('Equal nonempty altitude and density arrays required')
    if any(not isfinite(float(h)) for h in altitude_km) or any(not isfinite(float(n)) or n<0 for n in ne_m3):
        raise ValueError('Invalid altitude/density')
    if any(b<=a for a,b in zip(altitude_km,altitude_km[1:])):
        raise ValueError('Altitudes must increase strictly')
    out={}
    for layer,(lo,hi) in BANDS_KM.items():
        pts=[(float(h),float(n)) for h,n in zip(altitude_km,ne_m3) if lo<=h<hi]
        if pts:
            h,n=max(pts,key=lambda x:x[1]);out[layer]={'band_max_ne_m3':n,'band_max_altitude_km':h,'peak_confirmed':False}
        else:out[layer]={'band_max_ne_m3':None,'band_max_altitude_km':None,'peak_confirmed':False}
    return out

def integrated_tec_tecu(altitude_km,ne_m3):
    """Vertical integral of supplied profile; caller must specify topside coverage."""
    describe_layers(altitude_km,ne_m3)
    return sum((altitude_km[i+1]-altitude_km[i])*1000*(ne_m3[i+1]+ne_m3[i])/2 for i in range(len(altitude_km)-1))/1e16
