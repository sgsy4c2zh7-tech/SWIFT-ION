import {test} from 'node:test';
import assert from 'node:assert/strict';
import {HEIGHT_LAYERS,atHeight,neAt,getWeights,distanceKm,parseRoute,routeSamples,texturePixels,gridIsosurface,rgba} from '../docs/shared/gaia3d.mjs';
const altitudes=[100,200,300,400,600,800,1000];
const sites=[];
for(let lat=25;lat<=45;lat+=5)for(let lon=125;lon<=145;lon+=5){
 const peak=300+(lat-35)*2;
 sites.push({lat,lon,ne_log10_m3:altitudes.map(a=>Math.log10(1e9+9e11*Math.exp(-.5*((a-peak)/115)**2)))});
}
test('distinct representative shell altitudes are valid',()=>{
 assert.deepEqual(HEIGHT_LAYERS.map(l=>l.height),[125,190,300,650]);
});
test('interpolation is linear in electron density, not in logarithm',()=>{
 const s={ne_log10_m3:[10,12]};
 const a=atHeight(s,150,[100,200]);
 assert.ok(Math.abs(a-Math.log10((1e10+1e12)/2))<1e-10);
});
test('IDW is exact at a source point',()=>{
 const w=getWeights(sites,35,135,'japan');
 assert.equal(w.length,1);
 const p=neAt(sites,w,300,altitudes);
 assert.ok(Math.abs(p-sites.find(s=>s.lat===35&&s.lon===135).ne_log10_m3[2])<1e-9);
});
test('Japan coverage does not extrapolate across oceans',()=>{
 assert.deepEqual(getWeights(sites,-40,90,'japan'),[]);
});
test('texture alpha follows density and null stays transparent',()=>{
 const near=rgba(12,'turbo',.7); const low=rgba(8,'turbo',.7);
 assert.ok(near[3]>low[3]);assert.equal(rgba(null)[3],0);
 const px=texturePixels(sites,altitudes,{west:125,east:145,south:25,north:45},24,14,300,'viridis',.8,'japan');
 assert.equal(px.length,24*14*4);
 assert.ok(px.some(x=>x>0));
});
test('route can be parsed and crosses waypoints',()=>{
 const route=parseRoute('35.68, 139.76\n34.7, 135.5\n26.21, 127.68');
 const s=routeSamples(route,20);
 assert.equal(route.length,3);assert.equal(s.length,21);
 assert.ok(distanceKm(s[0].lat,s[0].lon,route[0][0],route[0][1])<.01);
 assert.ok(distanceKm(s.at(-1).lat,s.at(-1).lon,route.at(-1)[0],route.at(-1)[1])<.01);
});
test('route validation rejects out-of-bounds coordinates',()=>{
 assert.throws(()=>parseRoute('100,0\n0,0'));assert.throws(()=>parseRoute('1,2'));
});
test('isosurface triangulates a simulated F2 peak',()=>{
 const b={west:125,east:145,south:25,north:45};
 const iso=gridIsosurface(sites,altitudes,b,11.2,'japan',11,9,9);
 assert.ok(iso.triangles.length>0,'iso should intersect peak layer');
 for(const tri of iso.triangles.slice(0,10))for(const v of tri)assert.equal(v.length,3);
});
test('threshold beyond model density yields no isosurface',()=>{
 const iso=gridIsosurface(sites,altitudes,{west:125,east:145,south:25,north:45},14,'japan',9,7,7);
 assert.equal(iso.triangles.length,0);
});
