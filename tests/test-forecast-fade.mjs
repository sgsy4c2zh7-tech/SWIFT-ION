import assert from 'node:assert/strict';
import {coverageAlpha,COVERAGE_LIMIT_KM} from '../docs/shared/forecast-fade.mjs';
assert.equal(coverageAlpha(0,'japan'),1);
assert.equal(coverageAlpha(250,'japan'),1);
assert.equal(coverageAlpha(1100,'japan'),0);
assert.equal(coverageAlpha(3800,'global'),0);
assert.equal(coverageAlpha(Infinity,'japan'),0);
assert.equal(coverageAlpha(NaN,'japan'),0);
for(let d=250;d<1100;d+=25){
 assert.ok(coverageAlpha(d,'japan')>=coverageAlpha(d+25,'japan'));
 assert.ok(coverageAlpha(d,'japan')>=0 && coverageAlpha(d,'japan')<=1);
}
console.log('Forecast coverage alpha: OK');
