import assert from 'node:assert/strict';
import {qualityClues,missingClues,windowFromForecast} from '../docs/shared/fof2-window-diagnostics.mjs';
const t='2026-11-23T00:00:00Z';
const frames=[
 {valid_at:t,sites:[{lat:35.7,lon:139.5,fof2_quality:'STANDARD',scenario_status:'SCENARIO_AVAILABLE'}]},
 {valid_at:'2026-11-23T00:30:00Z',sites:[{lat:35.7,lon:139.5,fof2_quality:'EXTENDED',scenario_status:'EXTENDED_RATIO_LOW'}]},
 {valid_at:'2026-11-23T01:00:00Z',sites:[{lat:35.7,lon:139.5,fof2_quality:'MISSING',scenario_status:'VTEC_MISSING'}]}
];
const bounds=windowFromForecast(frames,'all');
const station={id:'KOKUBUNJI',lat:35.71,lon:139.49};
const quality=qualityClues(frames,station,bounds);
assert.deepEqual(quality,{standard:1,extended:1,missing:1,total:3});
const rows=[
 {station:'KOKUBUNJI',ms:Date.parse(frames[0].valid_at),model_mhz:7},
 {station:'KOKUBUNJI',ms:Date.parse(frames[1].valid_at),model_mhz:7.3},
 {station:'KOKUBUNJI',ms:Date.parse(frames[2].valid_at),model_mhz:null}
];
const missing=missingClues(frames,rows,station,bounds);
assert.equal(missing.missing,1);assert.equal(missing.counts.VTEC_MISSING,1);
console.log('foF2 normal / provisional / missing quality diagnostics passed');
