import assert from 'node:assert/strict';
import {PRESET_ROUTES,computeRoute,metricAtSite,sampleSpatial,sampleSpacetime,profileAlongRoute,routeSummary} from '../docs/shared/route-forecast.mjs';
const utc='2026-11-21T00:00:00Z';
const site=(lat,lon,fof2=9)=>({lat,lon,fof2_iri_mhz:fof2,fof2_tec_mhz:fof2*1.1,hmf2_iri_km:320,
 vtec_forecast_tecu:20,iri_ne_log10_m3:[10,11,12],tec_ne_log10_m3:[10.1,11.1,12.1]});
const sites=[site(35.68,139.76,8),site(32,135,9),site(26.21,127.68,10),site(39,142,7)];
const payload={altitudes_km:[100,300,500],frames:[{valid_at:utc,sites},
 {valid_at:'2026-11-21T00:30:00Z',sites:sites.map(s=>({...s,fof2_iri_mhz:s.fof2_iri_mhz+1,fof2_tec_mhz:s.fof2_tec_mhz+1}))},
 {valid_at:'2026-11-21T01:00:00Z',sites:sites.map(s=>({...s,fof2_iri_mhz:s.fof2_iri_mhz+2,fof2_tec_mhz:s.fof2_tec_mhz+2}))}]};
assert.equal(Object.keys(PRESET_ROUTES).length,5);
assert.equal(computeRoute(PRESET_ROUTES['tokyo-naha']).length,61);
assert.equal(metricAtSite(sites[0],'fof2','iri'),8);
assert.equal(metricAtSite(sites[0],'fof2','tec'),8.8);
assert.equal(metricAtSite(sites[0],'hmf2','tec'),320);
assert.equal(sampleSpatial(payload.frames[0],35.68,139.76,'fof2','iri'),8);
assert.equal(sampleSpacetime(payload,35.68,139.76,Date.parse('2026-11-21T00:15:00Z'),'fof2'),8.5);
assert.equal(sampleSpacetime(payload,35.68,139.76,Date.parse('2026-11-20T00:00:00Z'),'fof2'),null);
assert.equal(sampleSpacetime(payload,35.68,139.76,Date.parse('2026-11-21T03:00:00Z'),'fof2'),null);
const one=profileAlongRoute(payload,PRESET_ROUTES['tokyo-naha'],0,{count:8,travel:false});
assert.equal(one.length,9);assert.equal(one.at(0).valid_at,new Date(utc).toISOString());
const travel=profileAlongRoute(payload,PRESET_ROUTES['tokyo-naha'],0,{count:8,travel:true,durationHours:1});
assert.equal(travel.at(-1).valid_at,'2026-11-21T01:00:00.000Z');
assert(travel.at(-1).value>one.at(-1).value);
assert(routeSummary(travel).coverage>0);
assert.equal(sampleSpatial({sites:sites.map(s=>({...s,fof2_tec_mhz:null}))},35.68,139.76,'fof2','tec'),null);
assert.equal(metricAtSite(sites[0],'ne','iri',[100,300,500],300),11);
assert.throws(()=>profileAlongRoute(payload,PRESET_ROUTES['tokyo-naha'],0,{durationHours:40}));
console.log('route forecast: 15 assertions OK');
