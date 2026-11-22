import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {workbookBlob} from '../docs/shared/xlsx-charts.mjs';
const names=['WAKKANAI','KOKUBUNJI','YAMAGAWA','OKINAWA'];
const rows=[['Elapsed hours',...names.map(n=>`${n} predicted`),...names.map(n=>`${n} observed`)]];
for(let i=0;i<241;i++){rows.push([i*.5,...names.map((_,n)=>7+n+i*.01),...names.map(()=>null)]);}
const charts=names.map((n,i)=>({title:n+' foF2',xCol:0,yCols:[i+1,i+5],anchorCol:11,anchorRow:1+i*21,endCol:23,endRow:19+i*21,labelStride:12}));
const result=workbookBlob([{name:'foF2_Charts',rows,charts}]);assert(result.size>20000);
if(process.env.TEST_XLSX_PATH)await writeFile(process.env.TEST_XLSX_PATH,Buffer.from(await result.arrayBuffer()));
console.log('4-station native chart export passed',result.size);
