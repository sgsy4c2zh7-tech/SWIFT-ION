import assert from 'node:assert/strict';
import {drawAxisPlot,oneMhzBounds,sixDayUtcBounds,tickValues} from '../docs/shared/axis-plots.mjs';

// MHz bounds only from visible valid values; fractions rounded outward.
assert.deepEqual(oneMhzBounds([null,NaN,4.21,13.77]),{min:4,max:14,available:true});
assert.deepEqual(oneMhzBounds([10,10]),{min:9,max:11,available:true});
assert.deepEqual(oneMhzBounds([null,undefined,NaN]),{min:0,max:1,available:false});
assert.deepEqual(tickValues(4,14,1),[4,5,6,7,8,9,10,11,12,13,14]);

const start=Date.parse('2026-11-22T13:30:00Z');
const six=sixDayUtcBounds(start);
assert.equal(new Date(six.start).toISOString(),'2026-11-22T00:00:00.000Z');
assert.equal(new Date(six.end).toISOString(),'2026-11-28T00:00:00.000Z');
assert.equal(six.end-six.start,144*3600000);
assert.throws(()=>sixDayUtcBounds(NaN));

// Stub canvas validates generated axis labels without loading a browser or source data.
globalThis.window={devicePixelRatio:1};
const text=[];
const ctx={
 setTransform(){},fillRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},
 strokeRect(){},save(){},translate(){},rotate(){},restore(){},setLineDash(){},
 fillText(s){text.push(String(s));}
};
const canvas={clientWidth:800,clientHeight:460,dataset:{},getContext(){return ctx},
 addEventListener(){},getBoundingClientRect(){return {left:0}}};
const points=[];
for(let i=0;i<=240;i++)points.push({x:start+i*1800000,y:4.25+9*Math.abs(Math.sin(i*.12))});
drawAxisPlot(canvas,[{name:'forecast',color:'#66ffff',points}],{
 kind:'time',timeStyle:'nict',xMin:six.start,xMax:six.end,step:6*3600000,
 yMin:4,yMax:14,yStep:1,title:'foF2',valueUnit:'MHz'
});
for(let x=4;x<=14;x++)assert(text.includes(String(x)),`Missing ${x} MHz gridline`);
for(const d of ['11/22','11/23','11/24','11/25','11/26','11/27'])assert(text.includes(d),`Missing day ${d}`);
assert(text.includes('00')&&text.includes('12'));
console.log('NICT 6-day UTC axis and 1-MHz labels: passed');
