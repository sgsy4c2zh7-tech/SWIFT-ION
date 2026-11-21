import test from 'node:test';
import assert from 'node:assert/strict';
import {latitudeAtMercatorFraction,mercatorFractionAtLatitude,mercatorY} from '../docs/shared/map-geo.mjs';

test('north and south bounds preserved',()=>{
 assert.ok(Math.abs(latitudeAtMercatorFraction(47,23,0)-47)<1e-10);
 assert.ok(Math.abs(latitudeAtMercatorFraction(47,23,1)-23)<1e-10);
});
test('Web Mercator conversion round trips for Japan and global latitudes',()=>{
 for(const [n,s] of [[47,23],[75,-75]])for(const lat of [n,s,(n+s)/2,n*.4+s*.6]){
  const f=mercatorFractionAtLatitude(n,s,lat);
  assert.ok(Math.abs(latitudeAtMercatorFraction(n,s,f)-lat)<1e-8);
 }
});
test('Mercator 50 percent differs from arithmetic latitude midpoint',()=>{
 const halfway=latitudeAtMercatorFraction(47,23,.5);
 assert.ok(Math.abs(halfway-35)>.2);
});
test('reject invalid bounds',()=>{
 assert.throws(()=>latitudeAtMercatorFraction(23,47,.5),RangeError);
 assert.throws(()=>latitudeAtMercatorFraction(47,23,2),RangeError);
 assert.throws(()=>mercatorY(90),RangeError);
});
