/** Fine-grained, UTC-safe canvas charts for SWIFT-ION. No fabricated samples. */
export function tickValues(min,max,step){
 if(!Number.isFinite(min)||!Number.isFinite(max)||!Number.isFinite(step)||step<=0||max<=min)return [];
 const first=Math.ceil((min-1e-9*step)/step)*step;const out=[];
 for(let value=first;value<=max+1e-8*step&&out.length<1000;value+=step)out.push(Math.round(value*1e6)/1e6 || 0);
 return out;
}
/** Display bounds snapped to EVERY integer MHz, from values within the visible window.
 * Missing values must not affect the axis; no fabricated measurements.
 */
export function oneMhzBounds(values){
 const nums=values.filter(Number.isFinite);
 if(!nums.length)return {min:0,max:1,available:false};
 let min=Math.floor(Math.min(...nums)),max=Math.ceil(Math.max(...nums));
 if(max<=min){min=Math.max(0,min-1);max=min+2;}
 return {min,max,available:true};
}
/** NICT-style six UTC calendar days, aligned to midnight for comparable day labels.
 * The forecast may be shorter; the rest is deliberately BLANK.
 */
export function sixDayUtcBounds(firstValidMs){
 if(!Number.isFinite(firstValidMs))throw Error('First forecast UTC is invalid');
 const dayMs=86400000;
 const start=Math.floor(firstValidMs/dayMs)*dayMs;
 return {start,end:start+6*dayMs};
}
const chartState=new WeakMap();
function formatTime(x,span){let date=new Date(x);if(!Number.isFinite(date.valueOf()))return '—';
 const hh=String(date.getUTCHours()).padStart(2,'0'),mm=String(date.getUTCMinutes()).padStart(2,'0');
 return span>=36*3600000?`${String(date.getUTCMonth()+1).padStart(2,'0')}/${String(date.getUTCDate()).padStart(2,'0')} ${hh}:${mm}`:`${hh}:${mm}`;
}
function labelFor(x,opts,span){return opts.kind==='time'?formatTime(x,span):`${Math.round(x)}`;}
function crosshairDetail(x,series,opts){let str=opts.kind==='time'?new Date(x).toISOString().slice(0,16).replace('T',' ')+' UTC':`${x.toFixed(1)} ${opts.unit||''}`;
 for(const s of series){const pts=s.points.filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y));if(!pts.length)continue;
  let nearest=pts[0];for(const p of pts)if(Math.abs(p.x-x)<Math.abs(nearest.x-x))nearest=p;
  if(Math.abs(nearest.x-x)<=(opts.hoverTolerance??Infinity))str+=`\n${s.name}: ${nearest.y.toFixed(2)} ${opts.valueUnit||'MHz'}`;
 }
 return str;
}
export function drawAxisPlot(canvas,series,opts={}){
 const dpr=Math.min(2,window.devicePixelRatio||1),w=Math.max(260,canvas.clientWidth||520),h=Math.max(210,canvas.clientHeight||260);
 canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
 const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
 const xmin=Number(opts.xMin??Math.min(...series.flatMap(s=>s.points.map(p=>p.x)).filter(Number.isFinite)));
 const xmax=Number(opts.xMax??Math.max(...series.flatMap(s=>s.points.map(p=>p.x)).filter(Number.isFinite)));
 const values=series.flatMap(s=>s.points.map(p=>p.y)).filter(Number.isFinite);
 const ymax=Number(opts.yMax??Math.max(8,Math.ceil(Math.max(...values,8)/2)*2));
 const ymin=Number(opts.yMin??0), xlo=Number.isFinite(xmin)?xmin:0, xhi=xmax>xlo?xmax:xlo+1;
 const nictStyle=opts.kind==='time'&&opts.timeStyle==='nict';
 const left=51,right=w-16,top=22,bottom=h-(nictStyle?80:61);
 ctx.fillStyle='#081c2c';ctx.fillRect(0,0,w,h);
 const xp=x=>left+(x-xlo)/(xhi-xlo)*(right-left),yp=y=>bottom-(y-ymin)/(ymax-ymin)*(bottom-top);
 const requested=Number(opts.step??(xhi-xlo)/6);
 let step=requested;while((xhi-xlo)/step>(right-left)/Math.max(40,opts.kind==='time'?56:30))step*=2;
 const ticks=tickValues(xlo,xhi,step);
 ctx.font='10px system-ui';
 const yStep=Number(opts.yStep);
 if(Number.isFinite(yStep)&&yStep>0){
   // Every 1 MHz must be visible; caller gives canvas enough vertical height.
   for(const yValue of tickValues(ymin,ymax,yStep)){
     const y=yp(yValue);
     ctx.strokeStyle='#234960';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();
     ctx.fillStyle='#c7dcec';ctx.textAlign='right';ctx.font='11px system-ui';
     ctx.fillText(Number.isInteger(yValue)?String(yValue):String(yValue),left-7,y+4);
   }
 }else{
   for(let n=0;n<=5;n++){
     const y=top+(bottom-top)*n/5;
     ctx.strokeStyle='#234960';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();
     ctx.fillStyle='#bcd4e5';ctx.textAlign='right';ctx.fillText((ymax-(ymax-ymin)*n/5).toFixed(1),left-7,y+3);
   }
 }
 ctx.textAlign='center';
 if(nictStyle){
   // Dates centered under each UTC day, plus 6-hour gridlines (major at 00 UTC).
   const hourMs=3600000,dayMs=86400000,base=Math.floor(xlo/dayMs)*dayMs;
   const labelEveryHours=(right-left)/((xhi-xlo)/(6*hourMs))>=42?6:
     (right-left)/((xhi-xlo)/(12*hourMs))>=32?12:24;
   const nictStep=Number(opts.step)>0?Number(opts.step):6*hourMs;
   for(let x=base;x<=xhi+1;x+=nictStep){
     if(x<xlo-1||x>xhi+1)continue;
     const xPx=xp(x),date=new Date(x),hour=date.getUTCHours();
     const midnight=hour===0;
     ctx.strokeStyle=midnight?'#4a769a':'#2d5068';ctx.lineWidth=midnight?1.2:0.7;
     ctx.beginPath();ctx.moveTo(xPx,top);ctx.lineTo(xPx,bottom);ctx.stroke();
     if(hour%labelEveryHours===0){
       ctx.fillStyle='#bed8e9';ctx.textAlign='center';ctx.font='10px system-ui';
       ctx.fillText(String(hour).padStart(2,'0'),xPx,bottom+15);
     }
   }
   for(let day=base;day<xhi;day+=dayMs){
     const middle=Math.max(xlo,day)+(Math.min(xhi,day+dayMs)-Math.max(xlo,day))/2;
     if(middle<xlo||middle>xhi)continue;
     const d=new Date(day),date=`${String(d.getUTCMonth()+1).padStart(2,'0')}/${String(d.getUTCDate()).padStart(2,'0')}`;
     ctx.fillStyle='#9fe4fa';ctx.textAlign='center';ctx.font='11px system-ui';
     ctx.fillText(date,xp(middle),bottom+34);
   }
   ctx.textAlign='left';ctx.fillStyle='#99c1d6';ctx.font='10px system-ui';
   ctx.fillText('UTC 00 / 06 / 12 / 18 (6h補助線)   •   日付 MM/DD',left,h-15);
 }else{
   for(const t of ticks){const x=xp(t);if(x<left-1||x>right+1)continue;
     ctx.strokeStyle='#234960aa';ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,bottom);ctx.stroke();
     ctx.fillStyle='#bad7e9';ctx.save();ctx.translate(x,bottom+11);ctx.rotate(-Math.PI/5);ctx.textAlign='right';ctx.fillText(labelFor(t,opts,xhi-xlo),0,0);ctx.restore();
   }
 }
 ctx.strokeStyle='#587b93';ctx.strokeRect(left,top,right-left,bottom-top);
 for(const s of series){ctx.lineWidth=2.4;ctx.strokeStyle=s.color||'#76e0ed';ctx.beginPath();let open=false;
   for(const p of s.points){if(!Number.isFinite(p.x)||!Number.isFinite(p.y)||p.x<xlo||p.x>xhi){open=false;continue;}
    const x=xp(p.x),y=yp(p.y);if(!open){ctx.moveTo(x,y);open=true;}else ctx.lineTo(x,y);
   }ctx.stroke();
 }
 if(opts.hoverX!==undefined&&opts.hoverX!==null&&opts.hoverX>=xlo&&opts.hoverX<=xhi){const x=xp(opts.hoverX);
   ctx.setLineDash([4,4]);ctx.strokeStyle='#b9eff7';ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,bottom);ctx.stroke();ctx.setLineDash([]);
 }
 ctx.textAlign='left';ctx.fillStyle='#afcbdd';ctx.font='11px system-ui';ctx.fillText(opts.title||'foF2 (MHz)',left,13);
 ctx.textAlign='right';ctx.fillText(opts.kind==='time'?'UTC':opts.unit||'',right,h-7);ctx.textAlign='left';
 chartState.set(canvas,{series,opts:{...opts,xMin:xlo,xMax:xhi,step:requested},left,right,top,bottom});
 if(!canvas.dataset.axisBound){canvas.dataset.axisBound='1';
  canvas.addEventListener('pointermove',evt=>{
   const state=chartState.get(canvas);if(!state)return;
   const rect=canvas.getBoundingClientRect();const x=evt.clientX-rect.left;
   if(x<state.left||x>state.right){canvas.title='';return;}
   const xv=state.opts.xMin+(x-state.left)/(state.right-state.left)*(state.opts.xMax-state.opts.xMin);
   let nearest=null,delta=Infinity;
   for(const s of state.series){for(const p of s.points){if(!Number.isFinite(p.x))continue;const dx=Math.abs(p.x-xv);if(dx<delta){delta=dx;nearest=p.x;}}}
   if(nearest!==null){canvas.title=crosshairDetail(nearest,state.series,state.opts);}
  });
 }
}
