/** SWIFT-ION field.html: contour isolines / labels generated from the EXACT heatmap raster.
 * No external contour dependency.  Masked cells are never crossed.
 * Pixel-centre coordinates use Web Mercator, matching field.html heat rendering.
 */

export const CONTOUR_OPTIONS = Object.freeze({
  fof2: {unit:'MHz', steps:[0.5,1,2], preferred:1, lo:1, hi:18, decimals:1},
  hmf2: {unit:'km', steps:[25,50,100], preferred:50, lo:150, hi:550, decimals:0},
  tec: {unit:'TECU', steps:[2,5,10], preferred:5, lo:0, hi:100, decimals:1},
  // field.html's Ne value is log10 electron density, NOT raw m^-3.
  ne: {unit:'log₁₀ m⁻³', steps:[0.2,0.5,1], preferred:0.5, lo:8, hi:12.8, decimals:1},
});

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const mercatorY=(lat)=>Math.log(Math.tan(Math.PI/4+clamp(lat,-85,85)*Math.PI/360));
const deg=(y)=>Math.atan(Math.sinh(y))*180/Math.PI;

/** Raster pixel (x,y) indexes are cell centers; return their geographic center lat/lon. */
export function gridToLatLng(grid,x,y){
  const {nx,ny,bounds:b}=grid;
  const lon=b.w+(x+0.5)/nx*(b.e-b.w);
  const yf=(y+0.5)/ny;
  const my=mercatorY(b.n)+(mercatorY(b.s)-mercatorY(b.n))*yf;
  return [deg(my),lon];
}

export function makeLevels(lo,hi,step){
  if(!(Number.isFinite(step)&&step>0&&hi>lo))return [];
  const out=[];
  for(let n=Math.ceil((lo+1e-8)/step);n*step<hi-1e-8&&out.length<250;n++){
    out.push(Number((n*step).toFixed(6)));
  }
  return out;
}

/**
 * Marching squares. Grid = {nx,ny,values:Float32Array,mask:Uint8Array,bounds}.
 * Each point is [gridX,gridY]. Reject any square touching masked pixels to
 * prevent spurious zero-valued contours at missing-data coverage edges.
 */
export function contourSegments(grid,level){
  const {nx,ny,values,mask}=grid, segments=[];
  const at=(x,y)=>y*nx+x;
  for(let y=0;y<ny-1;y++)for(let x=0;x<nx-1;x++){
    const i0=at(x,y),i1=i0+1,i3=i0+nx,i2=i3+1;
    if(!mask[i0]||!mask[i1]||!mask[i2]||!mask[i3])continue;
    const v=[values[i0],values[i1],values[i2],values[i3]];
    if(v.some(z=>!Number.isFinite(z)))continue;
    const crossings=[];
    const edge=[[0,1],[1,2],[2,3],[3,0]];
    const corners=[[x,y],[x+1,y],[x+1,y+1],[x,y+1]];
    for(let e=0;e<4;e++){
      const [a,b]=edge[e];
      if((v[a]>=level)===(v[b]>=level))continue;
      const t=clamp((level-v[a])/(v[b]-v[a]),0,1);
      crossings[e]=[
        corners[a][0]+t*(corners[b][0]-corners[a][0]),
        corners[a][1]+t*(corners[b][1]-corners[a][1]),
      ];
    }
    const active=[0,1,2,3].filter(e=>crossings[e]);
    if(active.length===2)segments.push([crossings[active[0]],crossings[active[1]]]);
    else if(active.length===4){
      // Resolve saddle ambiguity consistently by the bilinear centre value.
      const centreHigh=(v[0]+v[1]+v[2]+v[3])/4>=level;
      const topLeftHigh=v[0]>=level;
      const pairs=centreHigh===topLeftHigh?[[0,1],[2,3]]:[[0,3],[1,2]];
      for(const [a,b] of pairs)segments.push([crossings[a],crossings[b]]);
    }
  }
  return segments;
}

/** Join adjacent marching-square segments into geographic polylines. */
export function stitchSegments(segments){
  if(!segments.length)return [];
  const key=p=>`${p[0].toFixed(5)},${p[1].toFixed(5)}`;
  const links=new Map();
  segments.forEach((s,i)=>s.forEach((p,end)=>{
    const k=key(p);if(!links.has(k))links.set(k,[]);
    links.get(k).push([i,end]);
  }));
  const used=new Uint8Array(segments.length),chains=[];
  for(let i=0;i<segments.length;i++){
    if(used[i])continue;
    used[i]=1;
    const chain=[segments[i][0],segments[i][1]];
    const extend=front=>{
      for(let watchdog=0;watchdog<segments.length;watchdog++){
        const current=front?chain[0]:chain[chain.length-1];
        const adj=links.get(key(current))||[];
        const next=adj.find(([j])=>!used[j]);
        if(!next)break;
        const [j,end]=next;used[j]=1;
        const other=segments[j][1-end];
        if(front)chain.unshift(other);else chain.push(other);
      }
    };
    extend(false);extend(true);
    if(chain.length>1)chains.push(chain);
  }
  return chains;
}

export function fieldContours(grid,lo,hi,step){
  return makeLevels(lo,hi,step).map(level=>({
    level,
    paths:stitchSegments(contourSegments(grid,level)),
  }));
}

const views=new WeakMap();
function ensureViews(map){
  if(views.has(map))return views.get(map);
  if(!map.getPane('swiftContoursPane')){
    map.createPane('swiftContoursPane');
    map.getPane('swiftContoursPane').style.zIndex='465';
    map.getPane('swiftContoursPane').style.pointerEvents='none';
  }
  const v={lines:L.layerGroup().addTo(map), contourLabels:L.layerGroup().addTo(map), numbers:L.layerGroup().addTo(map),
    renderer:L.canvas({pane:'swiftContoursPane',padding:0.3}), cache:null};
  views.set(map,v);return v;
}

function linesLength(points){
  let sum=0;
  for(let i=1;i<points.length;i++)sum+=Math.hypot(points[i][0]-points[i-1][0],points[i][1]-points[i-1][1]);
  return sum;
}
function midpoint(points){
  const total=linesLength(points);if(!total)return points[Math.floor(points.length/2)];
  let remaining=total/2;
  for(let i=1;i<points.length;i++){
    const a=points[i-1],b=points[i],d=Math.hypot(b[0]-a[0],b[1]-a[1]);
    if(remaining<=d){const t=d?remaining/d:0;return [a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])];}
    remaining-=d;
  }
  return points[points.length-1];
}
function pretty(level,conf){return Number(level).toFixed(conf.decimals).replace(/\.0$/,'');}
function addContourLabels(map,view,grid,contours,step,conf){
  if(!contours.length)return;
  const occupied=[];let count=0;
  const major=level=>Math.abs(level/(step*2)-Math.round(level/(step*2)))<1e-5;
  const candidates=[];
  for(const item of contours){
    if(!item.paths?.length)continue;
    const paths=[...item.paths].sort((a,b)=>linesLength(b)-linesLength(a)).slice(0,2);
    paths.forEach(path=>{
      const length=linesLength(path);
      if(length>3)candidates.push({level:item.level,point:midpoint(path),length,major:major(item.level)});
    });
  }
  candidates.sort((a,b)=>Number(b.major)-Number(a.major)||b.length-a.length);
  const size=map.getSize();
  for(const c of candidates){
    if(count>=24)break;
    const ll=gridToLatLng(grid,...c.point);
    if(!map.getBounds().contains(ll))continue;
    const xy=map.latLngToContainerPoint(ll);
    if(xy.x<44||xy.y<22||xy.x>size.x-44||xy.y>size.y-22)continue;
    if(occupied.some(p=>Math.hypot(p.x-xy.x,p.y-xy.y)<90))continue;
    occupied.push(xy);count++;
    const text=`${pretty(c.level,conf)} ${conf.unit}`;
    L.marker(ll,{interactive:false,keyboard:false,icon:L.divIcon({
      className:'swift-contour-label',html:`<span>${text}</span>`,iconSize:[92,21],iconAnchor:[46,10]
    })}).addTo(view.contourLabels);
  }
}
function addNumbers(map,view,grid,conf){
  // Sample the actual visible map (not a second interpolation). Screen-space spacing
  // avoids clutter while allowing dense values when zoomed into a small area.
  const size=map.getSize(),gap=Math.max(95,Math.min(145,130-8*(map.getZoom()-3)));
  const {nx,ny,bounds:b,values,mask}=grid;
  const myN=mercatorY(b.n),myS=mercatorY(b.s);
  const visited=new Set();let added=0;
  for(let py=gap/2;py<size.y&&added<125;py+=gap){
    for(let px=gap/2;px<size.x&&added<125;px+=gap){
      const ll=map.containerPointToLatLng([px,py]);
      if(ll.lng<b.w||ll.lng>b.e||ll.lat<b.s||ll.lat>b.n)continue;
      const x=clamp(Math.round((ll.lng-b.w)/(b.e-b.w)*nx-0.5),0,nx-1);
      const y=clamp(Math.round((mercatorY(ll.lat)-myN)/(myS-myN)*ny-0.5),0,ny-1);
      const i=y*nx+x;if(!mask[i]||!Number.isFinite(values[i])||visited.has(i))continue;
      visited.add(i);
      const text=pretty(values[i],conf);
      const actual=gridToLatLng(grid,x,y);
      L.marker(actual,{interactive:false,keyboard:false,icon:L.divIcon({
        className:'swift-value-label',html:`<span>${text}</span>`,iconSize:[56,21],iconAnchor:[28,10]
      })}).addTo(view.numbers);
      added++;
    }
  }
}

/** Called after field.html updates its heatmap image on each 30-minute frame.
 * options={metric,step,showContours,showContourLabels,showNumbers}
 */
export function drawFieldOverlays(map,grid,options){
  if(!map||!grid)return;
  const v=ensureViews(map);
  v.lines.clearLayers();v.contourLabels.clearLayers();v.numbers.clearLayers();
  const conf=CONTOUR_OPTIONS[options.metric]||CONTOUR_OPTIONS.fof2;
  const step=Number(options.step)>0?Number(options.step):conf.preferred;
  if(options.showContours||options.showContourLabels){
    if(!v.cache||v.cache.grid!==grid||v.cache.step!==step||v.cache.metric!==options.metric){
      v.cache={grid,step,metric:options.metric,contours:fieldContours(grid,conf.lo,conf.hi,step)};
    }
    const contours=v.cache.contours;
    if(options.showContours){
      contours.forEach(({level,paths})=>{
        if(!paths.length)return;
        const major=Math.abs(level/(step*2)-Math.round(level/(step*2)))<1e-5;
        const coords=paths.map(path=>path.map(point=>gridToLatLng(grid,...point)));
        L.polyline(coords,{pane:'swiftContoursPane',renderer:v.renderer,interactive:false,
          color:'#ffffff',opacity:major?0.97:0.65,weight:major?2.2:1.15,
          lineJoin:'round',lineCap:'round',smoothFactor:0}).addTo(v.lines);
      });
    }
    if(options.showContourLabels)addContourLabels(map,v,grid,contours,step,conf);
  }
  if(options.showNumbers)addNumbers(map,v,grid,conf);
}
