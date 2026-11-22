import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {tickValues} from '../docs/shared/axis-plots.mjs';
import {workbookBlob} from '../docs/shared/xlsx-charts.mjs';

assert.deepEqual(tickValues(0,260,100),[0,100,200]);
assert.deepEqual(tickValues(35,130,30),[60,90,120]);
assert.equal(tickValues(1,2,0).length,0);
const sheet=[['Distance km','foF2 MHz'],[0,8.2],[100,8.8],[200,null],[300,9.4]];
const wb=workbookBlob([{name:'Route_100km',rows:sheet,charts:[{title:'foF2 / distance',xCol:0,yCols:[1],anchorCol:4,anchorRow:1,endCol:16,endRow:20}]},
  {name:'Empty_data',rows:[['Note'],['Absence of observation data is not 0']]}]);
assert.ok(wb.size>4000);
if(process.env.TEST_XLSX_PATH)await writeFile(process.env.TEST_XLSX_PATH,Buffer.from(await wb.arrayBuffer()));
console.log('Axis tick tests and native Excel chart builder tests passed',wb.size);
