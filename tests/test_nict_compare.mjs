import assert from 'node:assert/strict';
import fs from 'node:fs';
const code=fs.readFileSync(new URL('../docs/shared/nict-compare.mjs',import.meta.url),'utf8').replace(/import \{sampleSpacetime\} from '\.\/route-forecast\.mjs';/,'const sampleSpacetime=()=>null;');
const {NICT_STATIONS,parseCsv,observationsFromCsv,matchForecast,stats,stationId}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
assert.equal(NICT_STATIONS.length,4);
assert.equal(stationId('国分寺'),'KOKUBUNJI');
const obs=observationsFromCsv('station,time_utc,fof2_mhz,source\nKOKUBUNJI,2026-11-21T01:15:00Z,8.2,NICT_manual\nWAKKANAI,2026-11-21T02:00:00Z,6.1,NICT_manual\n');
assert.equal(obs.observations.length,2);
const rows=[{station:'KOKUBUNJI',ms:Date.parse('2026-11-21T01:00:00Z'),model_mhz:8.4,time_utc:'2026-11-21T01:00:00Z'},
{station:'KOKUBUNJI',ms:Date.parse('2026-11-21T01:30:00Z'),model_mhz:8.5,time_utc:'2026-11-21T01:30:00Z'}];
const matched=matchForecast(rows,obs.observations);
assert.equal(matched.filter(x=>x.error_mhz!==null).length,1,'One observation must never match two forecasts');
assert.equal(stats(matched).n,1);
const bad=observationsFromCsv('station,time_utc,fof2_mhz\nKOKUBUNJI,2026-11-21T01:00:00,8');
assert.equal(bad.observations.length,0);
assert.equal(bad.warnings.length,1);
assert.deepEqual(parseCsv('a,b\n"x,y",z'),[['a','b'],['x,y','z']]);
console.log('NICT parser / timestamp / one-to-one matching: OK');
