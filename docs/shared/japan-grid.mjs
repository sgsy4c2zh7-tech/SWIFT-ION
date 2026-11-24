/* SWIFT-TEC ISEE regional forecast coordinates never wrap at +/-180 degrees.
 * Preserve missing-data margins and do not fill Japan with global NOAA samples. */
import {spatial as worldSpatial,interpolateColor} from './forecast.js';

function lower(values, x) {
 let lo=0,hi=values.length;
 while(lo<hi){const m=(lo+hi)>>1;if(values[m]<=x)lo=m+1;else hi=m}
 return lo;
}
export function sampleForecast(cube,values,lat,lon){
 if (!cube?.regional) return worldSpatial(cube,values,lat,lon);
 const ys=cube.latitudes, xs=cube.longitudes, nx=xs?.length||0,ny=ys?.length||0;
 if(nx<2||ny<2||!values||values.length!==nx*ny||!Number.isFinite(lat)||!Number.isFinite(lon)||
    lat<ys[0]||lat>ys[ny-1]||lon<xs[0]||lon>xs[nx-1])return null;
 const i=Math.min(ny-2,Math.max(0,lower(ys,lat)-1));
 const j=Math.min(nx-2,Math.max(0,lower(xs,lon)-1));
 const fy=(lat-ys[i])/(ys[i+1]-ys[i]);
 const fx=(lon-xs[j])/(xs[j+1]-xs[j]);
 const v=[values[i*nx+j],values[i*nx+j+1],values[(i+1)*nx+j],values[(i+1)*nx+j+1]];
 if(v.some(x=>x===null||!Number.isFinite(x)))return null;
 return ((v[0]*(1-fx)+v[1]*fx)*(1-fy)+(v[2]*(1-fx)+v[3]*fx)*fy)/cube.scale;
}
export function renderRegionalRaster(canvas,map,cube,now,prev=null,mode='vtec'){
 const size=map.getSize(),w=Math.min(680,Math.max(2,Math.ceil(size.x*.7))),h=Math.min(480,Math.max(2,Math.ceil(size.y*.7)));
 if(size.x<2||size.y<2)return;
 const temp=document.createElement('canvas');temp.width=w;temp.height=h;
 const ctx=temp.getContext('2d'),pixels=ctx.createImageData(w,h);
 const latitudes=new Float64Array(h),longitudes=new Float64Array(w);
 for(let x=0;x<w;x++)longitudes[x]=map.containerPointToLatLng([x*size.x/w,0]).lng;
 for(let y=0;y<h;y++)latitudes[y]=map.containerPointToLatLng([0,y*size.y/h]).lat;
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const v=sampleForecast(cube,now,latitudes[y],longitudes[x]);
  if(v==null)continue;
  let scale=v/100;
  if(mode==='delta30'){
    const old=sampleForecast(cube,prev,latitudes[y],longitudes[x]);
    if(old==null)continue;
    scale=(v-old+15)/30;
  }
  const rgba=interpolateColor(scale),k=(y*w+x)*4;
  pixels.data[k]=rgba[0];pixels.data[k+1]=rgba[1];pixels.data[k+2]=rgba[2];pixels.data[k+3]=rgba[3];
 }
 ctx.putImageData(pixels,0,0);
 const dpr=Math.min(2,window.devicePixelRatio||1);
 canvas.width=Math.round(size.x*dpr);canvas.height=Math.round(size.y*dpr);
 const out=canvas.getContext('2d');out.clearRect(0,0,canvas.width,canvas.height);out.imageSmoothingEnabled=true;
 out.drawImage(temp,0,0,canvas.width,canvas.height);
}
