/** SWIFT-ION v1.5 — numerics independent of Cesium.  IRI MODEL INTERPOLATION, NOT OBSERVATION. */
export const HEIGHT_LAYERS = Object.freeze([
  {id:'E', label:'E layer vicinity', height:125, color:'#3ac5e8'},
  {id:'F1',label:'F1 layer vicinity',height:190,color:'#51e0ba'},
  {id:'F2',label:'F2 layer vicinity',height:300,color:'#ffd36f'},
  {id:'top',label:'Topside',height:650,color:'#d99bff'}
]);
export const PALETTES={
  turbo:[[11,18,75],[34,81,185],[30,156,211],[54,204,154],[181,229,82],[255,210,49],[253,115,33],[211,40,50]],
  viridis:[[68,1,84],[71,44,122],[59,81,139],[44,113,142],[33,145,140],[59,176,116],[143,215,68],[253,231,37]],
  plasma:[[13,8,135],[75,3,161],[126,3,168],[168,34,150],[202,70,120],[230,109,89],[248,156,56],[240,249,33]],
  thermal:[[10,35,75],[15,85,150],[17,163,188],[48,216,157],[199,233,112],[255,199,91],[255,102,61],[238,56,132]]
};
export const LOG_MIN=8, LOG_MAX=12.8;
const PI=Math.PI, RAD=PI/180;
export function clamp(x,a,b){return Math.max(a,Math.min(b,x));}
export function longitude(lon){return ((lon+180)%360+360)%360-180;}
export function valid(n){return typeof n==='number' && Number.isFinite(n);}
export function distanceKm(la1,lo1,la2,lo2){
  const p1=la1*RAD,p2=la2*RAD,dp=(la2-la1)*RAD,dl=longitude(lo2-lo1)*RAD;
  const a=Math.sin(dp/2)**2+Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;
  return 12742*Math.asin(Math.min(1,Math.sqrt(Math.max(0,a))));
}
export function atHeight(site,alt,alts){
  if(!site || !Array.isArray(site.ne_log10_m3)||site.ne_log10_m3.length!==alts.length || alt<alts[0]||alt>alts.at(-1))return null;
  for(let i=0;i<alts.length;i++){
    if(alt===alts[i])return valid(site.ne_log10_m3[i])?site.ne_log10_m3[i]:null;
    if(i>0&&alts[i]>alt){
      const x=site.ne_log10_m3[i-1],y=site.ne_log10_m3[i];
      if(!valid(x)||!valid(y))return null;
      const f=(alt-alts[i-1])/(alts[i]-alts[i-1]);
      return Math.log10((1-f)*Math.pow(10,x)+f*Math.pow(10,y));
    }
  }
  return null;
}
/** IDW interpolation in *linear* electron density. Returns weighted source sites with nearest distance. */
export function getWeights(sites,lat,lon,source='global',maxSites=4){
  if(!Array.isArray(sites)||!sites.length)return [];
  let nearest=[];
  for(let i=0;i<sites.length;i++){
    let s=sites[i];if(!valid(s.lat)||!valid(s.lon))continue;
    const d=distanceKm(lat,lon,s.lat,s.lon);
    if(nearest.length<maxSites){nearest.push({i,d});nearest.sort((a,b)=>a.d-b.d);}
    else if(d<nearest.at(-1).d){nearest.pop();nearest.push({i,d});nearest.sort((a,b)=>a.d-b.d);}
  }
  if(!nearest.length || nearest[0].d>(source==='japan'?900:5100))return [];
  if(nearest[0].d<0.01)return [{i:nearest[0].i,w:1,nearest_km:nearest[0].d}];
  const d=nearest.map(n=>1/Math.max(n.d,40)**2),sum=d.reduce((a,b)=>a+b,0);
  return nearest.map((n,k)=>({i:n.i,w:d[k]/sum,nearest_km:nearest[0].d}));
}
export function neAt(sites,weights,alt,alts){
  let sum=0,w=0;
  for(const x of weights){const v=atHeight(sites[x.i],alt,alts);if(valid(v)){sum+=x.w*Math.pow(10,v);w+=x.w;}}
  return w?Math.log10(sum/w):null;
}
export function rgb(v,palette='turbo'){
  let anchors=PALETTES[palette]||PALETTES.turbo;
  const f=clamp((v-LOG_MIN)/(LOG_MAX-LOG_MIN),0,1)*(anchors.length-1);
  let i=Math.min(anchors.length-2,Math.floor(f)),t=f-i;
  return [0,1,2].map(j=>Math.round(anchors[i][j]*(1-t)+anchors[i+1][j]*t));
}
export function rgba(v,palette='turbo',opacity=.75){
  if(!valid(v))return [0,0,0,0];
  const c=rgb(v,palette);
  return [...c,Math.round(255*opacity*(.14+.86*clamp((v-LOG_MIN)/(LOG_MAX-LOG_MIN),0,1)))];
}
export function texturePixels(sites,alts,bounds,width,height,alt,palette,opacity,source='global'){
  const out=new Uint8ClampedArray(width*height*4);
  for(let y=0;y<height;y++){
    const lat=bounds.north-(y+.5)*(bounds.north-bounds.south)/height;
    for(let x=0;x<width;x++){
      const lon=bounds.west+(x+.5)*(bounds.east-bounds.west)/width;
      const w=getWeights(sites,lat,lon,source),v=neAt(sites,w,alt,alts),c=rgba(v,palette,opacity),o=4*(y*width+x);
      out[o]=c[0];out[o+1]=c[1];out[o+2]=c[2];out[o+3]=c[3];
    }
  }
  return out;
}
export function sphericalInterpolate(a,b,t){
  const vec=([lat,lon])=>{const p=lat*RAD,l=lon*RAD;return [Math.cos(p)*Math.cos(l),Math.cos(p)*Math.sin(l),Math.sin(p)];};
  const v=vec(a),w=vec(b),dot=clamp(v.reduce((s,x,i)=>s+x*w[i],0),-1,1),angle=Math.acos(dot);
  let p;if(angle<1e-6)p=v.map((x,i)=>x*(1-t)+w[i]*t);
  else if(PI-angle<1e-5){p=vec([a[0]*(1-t)+b[0]*t,a[1]*(1-t)+b[1]*t]);}
  else{let k=Math.sin((1-t)*angle)/Math.sin(angle),m=Math.sin(t*angle)/Math.sin(angle);p=v.map((x,i)=>k*x+m*w[i]);}
  const n=Math.hypot(...p);return [Math.asin(p[2]/n)/RAD,longitude(Math.atan2(p[1],p[0])/RAD)];
}
export function routeSamples(route,count=80){
  if(route.length<2)return [];
  const lengths=route.slice(1).map((b,i)=>distanceKm(...route[i],...b));
  const total=lengths.reduce((a,b)=>a+b,0),res=[];
  for(let k=0;k<=count;k++){
    const km=total*k/count;let j=0,base=0;
    while(j<lengths.length-1&&km>base+lengths[j])base+=lengths[j++];
    const t=lengths[j]?clamp((km-base)/lengths[j],0,1):0;
    const [lat,lon]=sphericalInterpolate(route[j],route[j+1],t);
    res.push({lat,lon,km});
  }
  return res;
}
export function parseRoute(text){
  const lines=String(text).trim().split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
  if(lines.length<2||lines.length>12)throw Error('2〜12地点の座標が必要です');
  return lines.map((s,i)=>{
    const values=s.split(/[\s,，]+/).filter(Boolean);
    if(values.length!==2)throw Error(`${i+1}行目: 緯度,経度 の形式で入力`);
    const p=values.map(Number);
    if(!p.every(valid)||Math.abs(p[0])>90||Math.abs(p[1])>180)throw Error(`${i+1}行目: 座標が範囲外`);
    return p;
  });
}
export function gridIsosurface(sites,alts,bounds,threshold,source='global',nx=16,ny=11,nz=9){
  // Marching tetrahedra; vertices are [lat, lon, altitude_km].  Input is IDW interpolated IRI climatology.
  const heights=Array.from({length:nz},(_,k)=>100+900*k/(nz-1));
  const grid=Array.from({length:nz},(_,k)=>Array.from({length:ny},(_,j)=>Array.from({length:nx},(_,i)=>{
    const lat=bounds.south+j*(bounds.north-bounds.south)/(ny-1),lon=bounds.west+i*(bounds.east-bounds.west)/(nx-1);
    const w=getWeights(sites,lat,lon,source);return {lat,lon,alt:heights[k],v:neAt(sites,w,heights[k],alts)};
  })));
  const corners=[[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]];
  const tets=[[0,5,1,6],[0,1,2,6],[0,2,3,6],[0,3,7,6],[0,7,4,6],[0,4,5,6]];
  const triangles=[];
  const mix=(a,b)=>{const f=clamp((threshold-a.v)/(b.v-a.v),0,1);return [a.lat+(b.lat-a.lat)*f,a.lon+(b.lon-a.lon)*f,a.alt+(b.alt-a.alt)*f];};
  for(let k=0;k<nz-1;k++)for(let j=0;j<ny-1;j++)for(let i=0;i<nx-1;i++){
    const vs=corners.map(([dx,dy,dz])=>grid[k+dz][j+dy][i+dx]);
    if(vs.some(v=>!valid(v.v)))continue;
    for(const tet of tets){
      const inside=tet.map(n=>vs[n]).filter(v=>v.v>=threshold),outside=tet.map(n=>vs[n]).filter(v=>v.v<threshold);
      if(!inside.length||!outside.length)continue;
      if(inside.length===1){const a=inside[0];triangles.push([mix(a,outside[0]),mix(a,outside[1]),mix(a,outside[2])]);}
      else if(inside.length===3){const a=outside[0];triangles.push([mix(a,inside[0]),mix(a,inside[2]),mix(a,inside[1])]);}
      else {const [a,b]=inside,[c,d]=outside;const p=mix(a,c),q=mix(a,d),r=mix(b,c),s=mix(b,d);triangles.push([p,q,r],[q,s,r]);}
      if(triangles.length>=28000)return {triangles,truncated:true};
    }
  }
  return {triangles,truncated:false};
}
