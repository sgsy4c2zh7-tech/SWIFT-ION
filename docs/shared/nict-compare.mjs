import {sampleSpacetime} from './route-forecast.mjs';
export const NICT_STATIONS=Object.freeze([
 {id:'WAKKANAI',name:'稚内／サロベツ',lat:45.16,lon:141.75},
 {id:'KOKUBUNJI',name:'国分寺',lat:35.71,lon:139.49},
 {id:'YAMAGAWA',name:'山川',lat:31.20,lon:130.62},
 {id:'OKINAWA',name:'沖縄／大宜味',lat:26.68,lon:128.15}
]);
export function stationId(raw){const x=String(raw||'').trim().toUpperCase().replace(/\s/g,'');return ({'稚内':'WAKKANAI','サロベツ':'WAKKANAI','稚内/サロベツ':'WAKKANAI','国分寺':'KOKUBUNJI','山川':'YAMAGAWA','沖縄':'OKINAWA','大宜味':'OKINAWA','OGIMI':'OKINAWA','SAROBETSU':'WAKKANAI'}[x]||x)}
export function parseCsv(txt){const rows=[];let row=[],value='',quoted=false;
 for(let i=0;i<txt.length;i++){let c=txt[i];if(quoted){if(c==='"'&&txt[i+1]==='"'){value+='"';i++}else if(c==='"')quoted=false;else value+=c;continue}if(c==='"')quoted=true;else if(c===','){row.push(value);value=''}else if(c==='\n'){row.push(value.replace(/\r$/,''));rows.push(row);row=[];value=''}else value+=c}
 if(quoted)throw Error('CSVのダブルクォートが閉じていません');if(value||row.length){row.push(value.replace(/\r$/,''));rows.push(row)}return rows;
}
export function observationsFromCsv(txt){const rows=parseCsv(txt.replace(/^\uFEFF/,''));if(rows.length<2)throw Error('CSVヘッダーと少なくとも1行が必要です');
 const header=rows[0].map(s=>s.trim().toLowerCase());const ix=k=>header.indexOf(k);
 for(const k of ['station','time_utc','fof2_mhz'])if(ix(k)<0)throw Error('必須列がありません: '+k);
 const out=[],warnings=[];
 for(const [i,row] of rows.slice(1).entries()){
  if(!row.join('').trim())continue;
  const st=stationId(row[ix('station')]);if(!NICT_STATIONS.some(x=>x.id===st)){warnings.push(`${i+2}行: 未知の観測所`);continue}
  const rawtime=row[ix('time_utc')]?.trim();if(!/(Z|[+-]\d\d:\d\d)$/i.test(rawtime||'')){warnings.push(`${i+2}行: UTC時刻のオフセットが不明`);continue}
  const ms=Date.parse(rawtime);if(!Number.isFinite(ms)){warnings.push(`${i+2}行: 日時が不正`);continue}
  const raw=row[ix('fof2_mhz')]?.trim(),v=raw===''?null:Number(raw);if(v!==null&&(!Number.isFinite(v)||v<=0||v>30)){warnings.push(`${i+2}行: foF2が範囲外`);continue}
  const source=ix('source')>=0?row[ix('source')]?.trim()||'ユーザーCSV':'ユーザーCSV';
  out.push({station:st,time_utc:new Date(ms).toISOString(),ms,fof2_mhz:v,source});
 }
 out.sort((a,b)=>a.ms-b.ms);return {observations:out,warnings};
}
export function extractForecast(payload,variant='iri'){
 if(payload?.schema!=='swift-ion-iri-tec-forecast-v1'||!Array.isArray(payload.frames))throw Error('予報JSONの形式が一致しません');
 return NICT_STATIONS.flatMap(st=>payload.frames.map(f=>{
  const ms=Date.parse(f.valid_at);
  const v=sampleSpacetime(payload,st.lat,st.lon,ms,'fof2',variant,300,'japan');
  return {station:st.id,station_name:st.name,time_utc:f.valid_at,ms,model_mhz:Number.isFinite(v)?+v.toFixed(3):null,is_prospective:!!f.is_prospective,variant};
 }));
}
/** Nearest observed point within ±15 min, unique observation can match only once per station. */
export function matchForecast(forecasts,observations,limitMin=15){
 // Greedy one-to-one matching by UTC proximity. A single observation cannot
 // inflate accuracy by matching multiple 30-minute forecast frames.
 const result=forecasts.map(f=>({...f,observed_mhz:null,obs_utc:null,observation_source:null,error_mhz:null}));
 const pairs=[];
 for(let i=0;i<forecasts.length;i++){
  const f=forecasts[i];if(f.model_mhz===null)continue;
  for(let j=0;j<observations.length;j++){
   const o=observations[j];if(o.station!==f.station||o.fof2_mhz===null)continue;
   const delta=Math.abs(o.ms-f.ms);if(delta<=limitMin*60000)pairs.push({i,j,delta});
  }
 }
 pairs.sort((a,b)=>a.delta-b.delta||a.i-b.i||a.j-b.j);
 const usedForecast=new Set(),usedObs=new Set();
 for(const p of pairs){if(usedForecast.has(p.i)||usedObs.has(p.j))continue;
  usedForecast.add(p.i);usedObs.add(p.j);
  const o=observations[p.j],f=forecasts[p.i];result[p.i].observed_mhz=o.fof2_mhz;
  result[p.i].obs_utc=o.time_utc;result[p.i].observation_source=o.source;
  result[p.i].error_mhz=+(f.model_mhz-o.fof2_mhz).toFixed(3);
 }
 return result;
}

export function stats(rows){const matched=rows.filter(x=>x.error_mhz!==null);if(!matched.length)return {n:0,mae:null,rmse:null,bias:null};const e=matched.map(x=>x.error_mhz);return {n:e.length,mae:e.reduce((s,x)=>s+Math.abs(x),0)/e.length,rmse:Math.sqrt(e.reduce((s,x)=>s+x*x,0)/e.length),bias:e.reduce((s,x)=>s+x,0)/e.length};}
