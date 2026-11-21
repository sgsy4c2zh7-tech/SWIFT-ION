/** Route-wise exploratory foF2 / hmF2 / Ne sampling of prospective IRI reference and TEC-linked sensitivity data.
 * Never represents a communication/MUF/aviation availability estimate. No synthetic fallback.
 */
import {distanceKm, routeSamples, getWeights, valid, atHeight} from './gaia3d.mjs';

export const PRESET_ROUTES = Object.freeze({
  'tokyo-naha': [[35.68,139.76],[26.21,127.68]],
  'sapporo-fukuoka': [[43.06,141.35],[33.59,130.40]],
  'sendai-osaka': [[38.27,140.87],[34.69,135.50]],
  'fukuoka-kagoshima': [[33.59,130.40],[31.60,130.56]],
  'tokyo-sydney': [[35.68,139.76],[-33.87,151.21]]
});
export const SAMPLE_COUNT=60;
export function computeRoute(route,count=SAMPLE_COUNT){return routeSamples(route,count)}

export function metricAtSite(s,metric,variant,altitudes=[],alt=300){
 if(!s)return null;
 if(metric==='fof2')return valid(variant==='tec'?s.fof2_tec_mhz:s.fof2_iri_mhz)?(variant==='tec'?s.fof2_tec_mhz:s.fof2_iri_mhz):null;
 if(metric==='hmf2')return valid(s.hmf2_iri_km)?s.hmf2_iri_km:null;
 if(metric==='tec')return valid(s.vtec_forecast_tecu)?s.vtec_forecast_tecu:null;
 if(metric==='ne'){
  const prof=variant==='tec'?s.tec_ne_log10_m3:s.iri_ne_log10_m3;
  const v=atHeight({ne_log10_m3:prof},alt,altitudes);
  return v;
 }
 return null;
}

/** IDW is local to model grid; cannot extrapolate beyond support or invent rejected scenario values. */
export function sampleSpatial(frame,lat,lon,metric='fof2',variant='iri',alts=[],alt=300,region='global'){
 if(!frame?.sites?.length)return null;
 const ws=getWeights(frame.sites,lat,lon,region);
 if(!ws.length)return null;
 let sum=0,den=0;
 for(const w of ws){
  const v=metricAtSite(frame.sites[w.i],metric,variant,alts,alt);
  if(!valid(v))continue;
  // Ne is stored logarithmically; aggregate Ne in linear units.
  sum+=w.w*(metric==='ne'?Math.pow(10,v):v);den+=w.w;
 }
 return den ? (metric==='ne'?Math.log10(sum/den):sum/den) : null;
}

/** Temporal interpolation uses two published valid frames; never extrapolates past forecast window. */
export function sampleSpacetime(payload,lat,lon,timeMs,metric='fof2',variant='iri',alt=300,region='global'){
 const ts=payload?.frames?.map(f=>Date.parse(f.valid_at))||[];
 if(!ts.length||!Number.isFinite(timeMs)||timeMs<ts[0]||timeMs>ts[ts.length-1])return null;
 let lo=0,hi=ts.length-1;
 while(hi-lo>1){const mid=Math.floor((lo+hi)/2);if(ts[mid]<=timeMs)lo=mid;else hi=mid}
 const a=sampleSpatial(payload.frames[lo],lat,lon,metric,variant,payload.altitudes_km,alt,region);
 if(ts[lo]===timeMs)return a;
 const b=sampleSpatial(payload.frames[hi],lat,lon,metric,variant,payload.altitudes_km,alt,region);
 if(a===null||b===null)return null;
 const t=(timeMs-ts[lo])/(ts[hi]-ts[lo]);
 return metric==='ne'?Math.log10((1-t)*Math.pow(10,a)+t*Math.pow(10,b)):(1-t)*a+t*b;
}

/** Route snapshot or time-of-passage series: flight duration is an illustrative user input. */
export function profileAlongRoute(payload,route,frameIndex,{metric='fof2',variant='iri',alt=300,region='global',travel=false,durationHours=3,count=SAMPLE_COUNT}={}){
 if(!payload?.frames?.length)throw Error('30-min forecast not published');
 if(frameIndex<0||frameIndex>=payload.frames.length)throw Error('Frame index invalid');
 if(!Number.isFinite(durationHours)||durationHours<=0||durationHours>36)throw Error('Flight duration must be 0..36 hours');
 const dep=Date.parse(payload.frames[frameIndex].valid_at);
 const points=computeRoute(route,count),lastKm=points.at(-1)?.km||0;
 return points.map(p=>{
  const fraction=lastKm>0?p.km/lastKm:0;
  const passage=dep+(travel?fraction*durationHours*3600000:0);
  const value=sampleSpacetime(payload,p.lat,p.lon,passage,metric,variant,alt,region);
  return {...p,valid_at:new Date(passage).toISOString(),value};
 });
}

export function routeSummary(points){
 const values=points.map(p=>p.value).filter(valid);
 if(!values.length)return {n:0,mean:null,min:null,max:null,coverage:0};
 return {n:values.length,mean:values.reduce((a,b)=>a+b,0)/values.length,min:Math.min(...values),max:Math.max(...values),coverage:values.length/points.length};
}
