/* SWIFT-ION shared 30-minute VTEC data contract; forecast only. No GNSS availability inference. */
export const L1_HZ=1575.42e6;
export const TECU_M_DELAY=(frequencyHz=L1_HZ)=>40.3e16/(frequencyHz*frequencyHz);
export const SWATCH=['#233c86','#386bb0','#53b7c4','#a7daaa','#f3dc7a','#f49b55','#ad3649'];
export const timestamp=s=>new Date(s).getTime();
export function normLon(x){return ((Number(x)+180)%360+360)%360-180}
export function interpolateColor(t,palette=SWATCH){
  if(!Number.isFinite(t))return [0,0,0,0];
  const n=palette.length-1,z=Math.max(0,Math.min(n-1e-8,t*n)),a=Math.floor(z),f=z-a;
  const parse=(p,i)=>parseInt(p.slice(1+2*i,3+2*i),16);
  return [0,1,2].map(i=>Math.round(parse(palette[a],i)*(1-f)+parse(palette[a+1],i)*f)).concat([191]);
}
function upperBound(items,x){let lo=0,hi=items.length;while(lo<hi){const m=(lo+hi)>>1;if(items[m]<=x)lo=m+1;else hi=m}return lo}
export function spatial(cube,values,lat,lon){
  const lats=cube.latitudes,lons=cube.longitudes, nx=lons.length;
  if(!values || !Number.isFinite(lat)||!Number.isFinite(lon)||lat<lats[0]||lat>lats.at(-1))return null;
  const k=upperBound(lats,lat);let i0=Math.max(0,Math.min(lats.length-2,k-1)),i1=i0+1;
  const fy=Math.max(0,Math.min(1,(lat-lats[i0])/(lats[i1]-lats[i0])));
  const y=((normLon(lon)-lons[0])%360+360)%360+lons[0];
  const e=upperBound(lons,y);let j0,j1,x0,x1;
  if(e>=nx){j0=nx-1;j1=0;x0=lons[j0];x1=lons[0]+360}
  else if(e<=0){j0=nx-1;j1=0;x0=lons[j0]-360;x1=lons[0]}
  else{j0=e-1;j1=e;x0=lons[j0];x1=lons[j1]}
  const fx=Math.max(0,Math.min(1,(y-x0)/(x1-x0)));
  const q=[values[i0*nx+j0],values[i0*nx+j1],values[i1*nx+j0],values[i1*nx+j1]];
  if(q.some(v=>v===null || !Number.isFinite(v)))return null;
  return ((q[0]*(1-fx)+q[1]*fx)*(1-fy)+(q[2]*(1-fx)+q[3]*fx)*fy)/cube.scale;
}
export function lookupTime(times,timeMs){
  if(!times.length)return null;
  if(timeMs<times[0]||timeMs>times.at(-1))return null;
  const after=upperBound(times,timeMs);
  if(after===0)return [0,0,0];
  if(after>=times.length)return [times.length-1,times.length-1,0];
  const before=after-1,f=(timeMs-times[before])/(times[after]-times[before]);return [before,after,f];
}
export class ForecastCube {
  constructor(base='./animation/'){this.base=base;this.cached=new Map();this.pending=new Map();}
  async load(){
    const r=await fetch(this.base+'index.json',{cache:'no-store'});if(!r.ok)throw Error('30分格子index HTTP '+r.status);
    this.index=await r.json();if(this.index.schema!=='swift-ion-vtec-animation-v1')throw Error('予報格子の形式が不正');
    this.latitudes=this.index.latitudes;this.longitudes=this.index.longitudes;
    this.times=this.index.time_utc.map(timestamp);this.scale=this.index.metadata.value_scale;
    this.nx=this.longitudes.length;this.ny=this.latitudes.length;
    if(this.scale!==10||this.times.length<2||this.index.metadata.time_step_minutes!==30)throw Error('時間分解能または単位が不一致');
    return this;
  }
  async frame(index){
    if(index<0||index>=this.times.length)throw Error('フレーム範囲外');
    const chunk=this.index.chunks.find(x=>x.start<=index && index<x.start+x.count);
    if(!chunk)throw Error('フレーム格納情報が欠落');
    if(this.cached.has(chunk.file)){const val=this.cached.get(chunk.file);this.cached.delete(chunk.file);this.cached.set(chunk.file,val);return val[index-chunk.start]}
    if(!this.pending.has(chunk.file))this.pending.set(chunk.file,fetch(this.base+chunk.file).then(r=>{if(!r.ok)throw Error('格子データ HTTP '+r.status);return r.json()}).then(d=>{
      if(d.start!==chunk.start||d.values.length!==chunk.count)throw Error('格子データの整合性エラー');
      this.cached.set(chunk.file,d.values);while(this.cached.size>5)this.cached.delete(this.cached.keys().next().value);
      return d.values;
    }).finally(()=>this.pending.delete(chunk.file)));
    return (await this.pending.get(chunk.file))[index-chunk.start];
  }
  async sampleAt(timeMs,lat,lon){
    const bracket=lookupTime(this.times,timeMs);if(!bracket)return null;
    const [a,b,t]=bracket;
    const v0=spatial(this,await this.frame(a),lat,lon);if(a===b)return v0;
    const v1=spatial(this,await this.frame(b),lat,lon);
    if(v0===null||v1===null)return null;
    return v0*(1-t)+v1*t;
  }
}
export function worldDistanceKm(a,b){
  const rad=Math.PI/180,la=a[0]*rad,lb=b[0]*rad,dl=(b[1]-a[1])*rad;
  const c=Math.sin(la)*Math.sin(lb)+Math.cos(la)*Math.cos(lb)*Math.cos(dl);
  return 6371*Math.acos(Math.max(-1,Math.min(1,c)));
}
export function greatCircle(a,b,f){
  const rad=Math.PI/180,va=xyz(a),vb=xyz(b);const theta=Math.acos(Math.max(-1,Math.min(1,va.reduce((s,x,i)=>s+x*vb[i],0))));
  const u=theta<1e-9?1-f:Math.sin((1-f)*theta)/Math.sin(theta),v=theta<1e-9?f:Math.sin(f*theta)/Math.sin(theta);
  const x=u*va[0]+v*vb[0],y=u*va[1]+v*vb[1],z=u*va[2]+v*vb[2];
  return [Math.atan2(z,Math.hypot(x,y))/rad,normLon(Math.atan2(y,x)/rad)];
}
export function xyz([lat,lon]){const a=lat*Math.PI/180,b=lon*Math.PI/180;return [Math.cos(a)*Math.cos(b),Math.cos(a)*Math.sin(b),Math.sin(a)]}
/* Bilinear raster for visualization. The smoothing does not create new model forecast skill. */
export function renderRaster(canvas,map,cube,now,previous=null,mode='vtec'){
  const w=Math.min(760,Math.ceil(map.getSize().x*0.7)),h=Math.min(420,Math.ceil(map.getSize().y*0.7));
  if(w<2||h<2)return;
  const off=document.createElement('canvas');off.width=w;off.height=h;
  const ctx=off.getContext('2d'),im=ctx.createImageData(w,h);
  const lons=new Float64Array(w),lats=new Float64Array(h);
  for(let x=0;x<w;x++)lons[x]=map.containerPointToLatLng([x*map.getSize().x/w,0]).lng;
  for(let y=0;y<h;y++)lats[y]=map.containerPointToLatLng([0,y*map.getSize().y/h]).lat;
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
    const value=spatial(cube,now,lats[y],lons[x]);if(value===null)continue;
    let t=value/100;
    if(mode==='delta30'){
      const old=spatial(cube,previous,lats[y],lons[x]);if(old===null)continue;
      t=(value-old+15)/30;
    }
    const rgba=interpolateColor(t);const p=(y*w+x)*4;
    im.data[p]=rgba[0];im.data[p+1]=rgba[1];im.data[p+2]=rgba[2];im.data[p+3]=rgba[3];
  }
  ctx.putImageData(im,0,0);
  canvas.width=map.getSize().x*devicePixelRatio;canvas.height=map.getSize().y*devicePixelRatio;
  const c=canvas.getContext('2d');c.clearRect(0,0,canvas.width,canvas.height);c.imageSmoothingEnabled=true;c.drawImage(off,0,0,canvas.width,canvas.height);
}
