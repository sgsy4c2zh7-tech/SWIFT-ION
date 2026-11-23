import assert from 'node:assert/strict';
import {tleEpochMs,invertMatrix,prepareSatellites,propagateSnapshot,solveIonoAt,buildGnssGrid,METERS_PER_TECU} from '../docs/shared/gnss-iono.mjs';
import {segmentsForLevel} from '../docs/shared/field-contour-canvas.mjs';
const line1='1 26407U 00040A   26327.02605608  .00000071  00000+0  00000+0 0  9996';
assert.equal(new Date(tleEpochMs(line1)).toISOString().slice(0,10),'2026-11-23');
assert.ok(METERS_PER_TECU>0.15&&METERS_PER_TECU<0.17);
const I=invertMatrix([[1,0,0,0],[0,2,0,0],[0,0,4,0],[0,0,0,8]]);
assert.ok(Math.abs(I[1][1]-0.5)<1e-12);
assert.equal(invertMatrix([[1,0,0,0],[0,1,0,0],[0,0,0,0],[0,0,0,1]]),null);
const snapshot={schema:'swift-ion-latest-gnss-v1',satellites:[
 {system:'gps',line1,line2:'2 demo',health:1},
 {system:'qzss',line1,line2:'2 demo',norad:'123'},
 {system:'galileo',line1,line2:'2 demo',norad:'124'},
 {system:'glonass',line1,line2:'2 demo',norad:'125'},
 {system:'beidou',line1,line2:'2 demo',norad:'126'},
]};
const fakeSat={twoline2satrec:()=>({}),propagate:()=>({position:{x:26560,y:500,z:500}}),eciToEcf:x=>x,gstime:()=>0};
const prepared=prepareSatellites(snapshot,fakeSat);assert.equal(prepared.length,4); // one unhealthy GPS excluded
assert.equal(propagateSnapshot(prepared,fakeSat,Date.parse('2026-11-28T00:00:00Z'),['qzss','galileo','glonass','beidou']).length,0);
assert.equal(propagateSnapshot(prepared,fakeSat,Date.parse('2026-11-23T00:00:00Z'),[]).length,0);
for (const system of ['qzss','galileo','glonass','beidou']) {
 const selected=propagateSnapshot(prepared,fakeSat,Date.parse('2026-11-23T00:00:00Z'),[system]);
 assert.equal(selected.length,1);assert.equal(selected[0].system,system);
}
assert.equal(propagateSnapshot(prepared,fakeSat,Date.parse('2026-11-23T00:00:00Z'),['qzss','galileo']).length,2);
assert.equal(solveIonoAt({},[],[],35,139),null);
const cube={latitudes:[-90,90],longitudes:[-180,0],nx:2,ny:2,scale:10};
const frame=[100,140,110,130];
// ECEF satellites with realistic GNSS ranges and independently distributed azimuth/elevation.
const directions=[[18000,0,10000],[21000,11000,7000],[18500,-11500,4000],[26000,8500,-14000],
 [23000,-10000,-12000],[17000,17000,-4000],[14000,-2000,20000],[15000,-16000,16000],
 [20000,19000,15000],[17000,-18000,-10000],[27000,8000,13000],[21000,3000,-18000]];
const satellites=directions.map(([x,y,z],i)=>({x,y,z,system:'gps',norad:String(i)}));
const result=solveIonoAt(cube,frame,satellites,0,0,10);
assert.ok(result,'Synthetic full-rank constellation must produce valid GNSS estimate');
assert.ok(result.iono_horizontal_m>=0&&result.iono_vertical_m>=0&&result.iono_bias_m>=0);
assert.ok(Math.abs(result.iono_horizontal_m**2+result.iono_vertical_m**2-result.iono_bias_m**2)<1e-6);
assert.ok(Math.abs(result.hdop**2+result.vdop**2-result.pdop**2)<1e-6);
const grid=buildGnssGrid(cube,frame,satellites,{latStep:30,lonStep:30});
for(const field of ['bias','biasH','biasV','dop','hdop','vdop'])assert.equal(grid[field].length,grid.nx*grid.ny);
const tiny={latitudes:[0,10],longitudes:[0,10],nx:2,ny:2};
assert.ok(segmentsForLevel(tiny,[0,10,10,0],5).length>=1);
assert.equal(segmentsForLevel(tiny,[0,null,10,0],5).length,0);
console.log('GNSS 5 constellation selection, H/V/3D, HDOP/VDOP, grid and contours PASS');
