import {HEIGHT_LAYERS,PALETTES,LOG_MIN,LOG_MAX,clamp,valid,distanceKm,atHeight,getWeights,neAt,rgb,rgba,texturePixels,parseRoute,routeSamples,gridIsosurface} from './gaia3d.mjs';
'use strict';
const $=id=>document.getElementById(id);
const ROUTES={
 'tokyo-naha':[[35.68,139.76],[26.21,127.68]],
 'sapporo-fukuoka':[[43.06,141.35],[33.59,130.40]],
 'sendai-osaka':[[38.27,140.87],[34.70,135.50]],
 'fukuoka-kagoshima':[[33.59,130.40],[31.60,130.56]],
 'tokyo-sydney':[[35.68,139.76],[-33.87,151.21]]
};
const q={data:null,forecast:null,source:'global',modelVariant:'iri',frame:0,mode:'multi',alt:300,palette:'turbo',opacity:.62,viewer:null,
  ownEntities:[],ownPrimitives:[],timer:null,route:ROUTES['tokyo-naha'],routePoints:[],selected:[35.68,139.76],lastSurfaceN:0,
  lastMode:null,rendering:false,revision:0,resizeTimer:null,weightCache:new Map(),pendingPose:false};
const BOUNDS={japan:{west:122,south:24,north:46,east:150},global:{west:-178,south:-75,north:75,east:178}};
const DATE_FORMAT=new Intl.DateTimeFormat('ja-JP',{timeZone:'UTC',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
const fmt=(n,d=1)=>valid(n)?n.toLocaleString('ja-JP',{maximumFractionDigits:d}):'—';
function status(t){$('status').textContent=t}
function isForecast(){return q.source==='forecast-global'||q.source==='forecast-japan'}
function sourceClass(){return q.source.endsWith('japan')?'japan':'global'}
function frames(){return isForecast()?(q.forecast?.frames||[]):sourceClass()==='japan'?(q.data?.japan?.frames||[]):(q.data?.global_frames||[])}
function frame(){return frames()[q.frame]}
function sites(){
  const f=frame();if(!f)return [];
  if(!isForecast())return sourceClass()==='japan'?(f.iri_sites||[]):(f.sites||[]);
  const regional=q.source==='forecast-japan';
  return (f.sites||[]).filter(s=>!regional||(s.lat>=23&&s.lat<=47&&s.lon>=121&&s.lon<=152)).map(s=>({
    ...s,ne_log10_m3:q.modelVariant==='tec'?s.tec_ne_log10_m3:s.iri_ne_log10_m3
  }));
}
function heights(){return isForecast()?(q.forecast?.altitudes_km||[]):(q.data?.metadata?.altitudes_km||[100,150,200,250,300,350,400,500,600,800,1000])}
function configBounds(){return BOUNDS[sourceClass()]}
function maxNearestKm(){return sourceClass()==='japan'?900:5100}
function weightsFor(ss,lat,lon){return getWeights(ss,lat,lon,sourceClass())}
function isFuture(){return isForecast()&&frame()?.is_prospective===true} 

function setMode(mode){
 q.mode=mode;
 document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));
 const labels={single:'SINGLE HEIGHT / COLOR MESH',multi:'MULTILAYER / TRANSLUCENT SHELLS',section:'3D CURTAIN / VERTICAL SECTION',voxel:'3D BOX VOXELS / COARSE MODEL',iso:'3D ISOSURFACE / MARCHING TETRAHEDRA',fof2:'foF2 / F2 LAYER CRITICAL FREQUENCY',hmf2:'hmF2 / F2 LAYER PEAK HEIGHT'};
 $('viewTitle').textContent=labels[mode]||mode;
 redraw();
}
function activeLayers(){return HEIGHT_LAYERS.filter(layer=>$('layer-'+layer.id)?.checked)}
function clearGraphics(){
 if(!q.viewer)return;
 for(const x of q.ownEntities)q.viewer.entities.remove(x);
 for(const x of q.ownPrimitives)q.viewer.scene.primitives.remove(x);
 q.ownEntities=[];q.ownPrimitives=[];
}
function applyBasemap(){
 if(!q.viewer)return;
 const layers=q.viewer.imageryLayers;layers.removeAll();
 const source=$('basemap')?.value||'osm';
 if(source==='grid'){q.viewer.scene.globe.show=true;q.viewer.scene.requestRender();return;}
 try{
  const url=source==='satellite'?'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}':
   'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
  layers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({url,maximumLevel:source==='satellite'?12:8,
    credit:new Cesium.Credit(source==='satellite'?'Esri World Imagery':'© OpenStreetMap contributors')}));
 }catch(err){console.error('Base map failed',err);status('地図レイヤーを表示できません: '+err.message)}
 q.viewer.scene.requestRender();
}
function createViewer(){
 if(!window.Cesium)throw Error('CesiumJSを読み込めません。CDN接続とブラウザのWebGL設定を確認してください。');
 Cesium.Ion.defaultAccessToken='';
 q.viewer=new Cesium.Viewer('globe',{baseLayerPicker:false,baseLayer:false,terrainProvider:new Cesium.EllipsoidTerrainProvider(),timeline:false,
   animation:false,geocoder:false,homeButton:true,sceneModePicker:false,selectionIndicator:false,infoBox:false,navigationHelpButton:false,
   fullscreenButton:false,requestRenderMode:true,maximumRenderTimeChange:Infinity});
 applyBasemap();
 q.viewer.scene.globe.enableLighting=false;
 q.viewer.scene.globe.depthTestAgainstTerrain=false;
 q.viewer.camera.setView({destination:Cesium.Cartesian3.fromDegrees(138,29,4300000)});
 q.viewer.scene.morphComplete.addEventListener(()=>{
  setProjectionControls();
  if(q.pendingPose){q.pendingPose=false;applyCameraPose()}
  q.viewer.resize();q.viewer.scene.requestRender();
 });
 const handler=new Cesium.ScreenSpaceEventHandler(q.viewer.canvas);
 handler.setInputAction(e=>{
   const ray=q.viewer.camera.getPickRay(e.position),p=ray&&q.viewer.scene.globe.pick(ray,q.viewer.scene);
   if(!p)return;
   const cart=Cesium.Cartographic.fromCartesian(p),lat=Cesium.Math.toDegrees(cart.latitude),lon=Cesium.Math.toDegrees(cart.longitude);
   if(!valid(lat)||!valid(lon))return;
   q.selected=[lat,lon];showSelection();drawProfile();drawIseeMap();q.viewer.scene.requestRender();
 },Cesium.ScreenSpaceEventType.LEFT_CLICK);
}
function cameraToData(){
 if(!q.viewer)return;
 const d=sourceClass()==='japan'?{lon:136,lat:35,height:2500000}:{lon:10,lat:10,height:14500000};
 q.viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
 q.viewer.camera.flyTo({destination:Cesium.Cartesian3.fromDegrees(d.lon,d.lat,d.height),duration:1.2});
}
function setProjectionControls(){
 if(!q.viewer)return;
 const m=q.viewer.scene.mode;
 const ids={scene3d:Cesium.SceneMode.SCENE3D,scene2d:Cesium.SceneMode.SCENE2D,scene25d:Cesium.SceneMode.COLUMBUS_VIEW};
 for(const [id,mode] of Object.entries(ids))$(id)?.classList.toggle('active-scene',m===mode);
 const flat=m===Cesium.SceneMode.SCENE2D;
 for(const id of ['cameraPitch','cameraHeading','cameraRange'])if($(id))$(id).disabled=flat;
 if(flat)$('cameraStatus').textContent='2D平面表示中：地図のズーム・ドラッグができます。横から見るには3Dへ切替。';
 else if(m===Cesium.SceneMode.COLUMBUS_VIEW)$('cameraStatus').textContent='2.5D斜め表示中。横からシェルを見るには「横から見る」を選択。';
}
function projection(mode){
 if(!q.viewer)return;
 const sc=q.viewer.scene;
 q.pendingPose=false;
 try{
  q.viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
  if(mode==='2d')sc.morphTo2D(.8);
  else if(mode==='25d')sc.morphToColumbusView(.8);
  else sc.morphTo3D(.8);
  $('cameraStatus').textContent='投影法を切替中…';
 }catch(e){$('cameraStatus').textContent='投影法の切替に失敗: '+e.message}
}
function applyCameraPose(){
 if(!q.viewer)return;
 const sc=q.viewer.scene;
 if(sc.mode!==Cesium.SceneMode.SCENE3D){
  q.pendingPose=true;
  q.viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
  if(sc.mode!==Cesium.SceneMode.MORPHING)sc.morphTo3D(.8);
  $('cameraStatus').textContent='3Dへ切り替えてカメラ角度を適用中…';
  return;
 }
 try{
  const [lat,lon]=q.selected?.every(valid)?q.selected:[35.68,139.76];
  const pitch=Number($('cameraPitch').value),heading=Number($('cameraHeading').value),range=Number($('cameraRange').value);
  const target=Cesium.Cartesian3.fromDegrees(lon,lat,300000);
  const look=new Cesium.HeadingPitchRange(Cesium.Math.toRadians(heading),Cesium.Math.toRadians(pitch),range*1000);
  q.viewer.camera.lookAt(target,look);
  q.viewer.scene.requestRender();setProjectionControls();
  $('cameraStatus').textContent=`${lat.toFixed(2)}°, ${lon.toFixed(2)}°を基準に視点設定：傾斜 ${pitch}°、方位 ${heading}°、距離 ${range} km。背景地図と層高度の位置関係を確認してください。`;
 }catch(e){$('cameraStatus').textContent='カメラ視点の設定に失敗: '+e.message}
}
function cameraPreset(kind){
 if(kind==='side'){
  $('cameraPitch').value='-12';$('cameraHeading').value='85';$('cameraRange').value='2200';
 }else{
  $('cameraPitch').value='-89';$('cameraHeading').value='0';$('cameraRange').value='4200';
 }
 for(const id of ['cameraPitch','cameraHeading','cameraRange'])$(id).dispatchEvent(new Event('input'));
 applyCameraPose();
}
function cachedGridWeights(w,hh){
 const sitesNow=sites(),b=configBounds();
 const key=[q.source,q.frame,w,hh,sitesNow.length].join(':');
 if(q.weightCache.has(key))return q.weightCache.get(key);
 const out=[];
 for(let y=0;y<hh;y++){
   const lat=b.north-(y+.5)*(b.north-b.south)/hh;
   for(let x=0;x<w;x++){
     const lon=b.west+(x+.5)*(b.east-b.west)/w;
     out.push(weightsFor(sitesNow,lat,lon));
   }
 }
 q.weightCache.clear();q.weightCache.set(key,out);
 return out;
}
function peakModel(site){
 const vals=site.ne_log10_m3||[],heightsNow=heights();let m=-Infinity,height=null;
 for(let i=0;i<Math.min(vals.length,heightsNow.length);i++){
   if(heightsNow[i]<180||heightsNow[i]>600||!valid(vals[i]))continue;
   if(vals[i]>m){m=vals[i];height=heightsNow[i]}
 }
 if(!valid(m))return {fof2:null,hmf2:null};
 return {fof2:8.98*Math.sqrt(Math.pow(10,m))/1e6,hmf2:height};
}
function characteristic(site,field){
 if(isForecast()){
  const v=field==='fof2'?(q.modelVariant==='tec'?site.fof2_tec_mhz:site.fof2_iri_mhz):site.hmf2_iri_km;
  return valid(v)?v:null;
 }
 const p=peakModel(site);return field==='fof2'?p.fof2:p.hmf2;
}
function mappedCharacteristic(ss,weights,field){
 let sum=0,wt=0;for(const n of weights){const v=characteristic(ss[n.i],field);
  if(valid(v)){sum+=n.w*v;wt+=n.w}}
 return wt?sum/wt:null;
}
function scalarColor(value,field,alpha){
 const low=field==='fof2'?1:150,high=field==='fof2'?18:550;
 if(!valid(value))return [0,0,0,0];
 const v=LOG_MIN+clamp((value-low)/(high-low),0,1)*(LOG_MAX-LOG_MIN);
 return rgba(v,q.palette,alpha);
}
function makeTexture(h,w,hh,multi=false,layerId=null){
 const c=document.createElement('canvas');c.width=w;c.height=hh;
 const ctx=c.getContext('2d'),pixels=new Uint8ClampedArray(w*hh*4);
 const alpha=q.opacity*(multi ? Number($('layerAlpha-'+layerId)?.value||65)/100 : 1),weights=cachedGridWeights(w,hh),ss=sites(),alts=heights();
 for(let i=0;i<weights.length;i++){
   const scalar=q.mode==='fof2'||q.mode==='hmf2';
   const v=scalar?mappedCharacteristic(ss,weights[i],q.mode):neAt(ss,weights[i],h,alts);
   const col=scalar?scalarColor(v,q.mode,alpha):rgba(v,q.palette,alpha),p=i*4;
   pixels[p]=col[0];pixels[p+1]=col[1];pixels[p+2]=col[2];pixels[p+3]=col[3];
 }
 ctx.putImageData(new ImageData(pixels,w,hh),0,0);return c;
}
function resolution(){
 const value=$('resolution').value;
 if(sourceClass()==='japan')return value==='low'?[72,58]:value==='high'?[200,144]:[132,102];
 return value==='low'?[104,66]:value==='high'?[232,126]:[168,90];
}
function addTextureShell(h,layerName,multi,layerId=null){
 const [w,hh]=resolution(),b=configBounds(),canvas=makeTexture(h,w,hh,multi,layerId);
 const entity=q.viewer.entities.add({name:layerName+' | IRI MODEL',rectangle:{coordinates:Cesium.Rectangle.fromDegrees(b.west,b.south,b.east,b.north),
   height:h*1000,material:new Cesium.ImageMaterialProperty({image:canvas,transparent:true}),outline:false}});
 q.ownEntities.push(entity);q.lastSurfaceN+=w*hh;
 return entity;
}
function drawRouteLines(includeWall=false){
 const pts=q.routePoints;
 if(pts.length<2)return;
 const positions=pts.flatMap(x=>[x.lon,x.lat,12*1000]);
 const e=q.viewer.entities.add({name:'Public illustrative route (not real flight plan)',polyline:{positions:Cesium.Cartesian3.fromDegreesArrayHeights(positions),
   width:3,material:Cesium.Color.fromCssColorString('#ffcf81'),clampToGround:false}});
 q.ownEntities.push(e);
 if(includeWall){
   const pos=Cesium.Cartesian3.fromDegreesArray(pts.flatMap(p=>[p.lon,p.lat]));
   q.ownEntities.push(q.viewer.entities.add({name:'MODEL CROSS SECTION CURTAIN',wall:{positions:pos,
     minimumHeights:pts.map(()=>100000),maximumHeights:pts.map(()=>1000000),
     material:Cesium.Color.fromCssColorString('#4bccf4').withAlpha(.14),outline:false}}));
 }
}
function addModelSiteDots(){
 const arr=sites();
 if(!arr.length)return;
 const group=new Cesium.PointPrimitiveCollection();
 for(const s of arr){const v=atHeight(s,q.alt,heights());if(!valid(v))continue;
   group.add({position:Cesium.Cartesian3.fromDegrees(s.lon,s.lat,q.alt*1000+8000),pixelSize:3.0,
     color:Cesium.Color.WHITE.withAlpha(.85),outlineColor:Cesium.Color.fromCssColorString('#133954'),outlineWidth:1});
 }
 q.ownPrimitives.push(q.viewer.scene.primitives.add(group));
}
function buildVoxels(){
 const b=configBounds(),det=$('voxelLimit').value==='detail';
 const nx=sourceClass()==='japan'?(det?14:11):(det?16:12),ny=sourceClass()==='japan'?(det?10:8):(det?10:8),
       hz=det?[130,185,250,325,430,570,730,900]:[140,210,310,450,650,880];
 const instances=[],threshold=Number($('iso').value)-.5;
 const latStep=(b.north-b.south)/ny,lonStep=(b.east-b.west)/nx;
 for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){
   const lat=b.south+(j+.5)*latStep,lon=b.west+(i+.5)*lonStep,w=weightsFor(sites(),lat,lon);
   if(!w.length)continue;
   for(let k=0;k<hz.length;k++){
     const h=hz[k],v=neAt(sites(),w,h,heights());if(!valid(v)||v<threshold)continue;
     const depth= k===0? (hz[1]-hz[0]) : (hz[k]-hz[k-1]);
     const dimX=111000*lonStep*Math.cos(lat*Math.PI/180)*.8,dimY=111000*latStep*.82,dimZ=Math.min(170000,depth*1000*.85);
     const pos=Cesium.Cartesian3.fromDegrees(lon,lat,h*1000);
     const col=rgb(v,q.palette);
     const geom=Cesium.BoxGeometry.fromDimensions({dimensions:new Cesium.Cartesian3(Math.max(5000,dimX),Math.max(5000,dimY),dimZ),
       vertexFormat:Cesium.PerInstanceColorAppearance.FLAT_VERTEX_FORMAT});
     instances.push(new Cesium.GeometryInstance({geometry:geom,modelMatrix:Cesium.Transforms.eastNorthUpToFixedFrame(pos),
       attributes:{color:Cesium.ColorGeometryInstanceAttribute.fromColor(new Cesium.Color(col[0]/255,col[1]/255,col[2]/255,.30*q.opacity+.10))}}));
   }
 }
 if(instances.length){
   q.ownPrimitives.push(q.viewer.scene.primitives.add(new Cesium.Primitive({geometryInstances:instances,
     appearance:new Cesium.PerInstanceColorAppearance({flat:true,translucent:true,closed:false}),asynchronous:true,allowPicking:false})));
 }
 q.lastSurfaceN=instances.length;
 $('renderInfo').textContent=`${instances.length} voxel boxes | 粗格子のモデル補間`;return instances.length;
}
function buildIsosurface(){
 const b=configBounds(),threshold=Number($('iso').value),det=$('voxelLimit').value==='detail';
 const result=gridIsosurface(sites(),heights(),b,threshold,sourceClass(),det?22:16,det?15:11,det?11:9);
 if(!result.triangles.length){$('renderInfo').textContent='該当する等電子密度面がありません（閾値変更可）';q.lastSurfaceN=0;return;}
 const positions=[],idx=[];
 for(const tri of result.triangles){for(const [lat,lon,h] of tri){const p=Cesium.Cartesian3.fromDegrees(lon,lat,h*1000);
   idx.push(positions.length/3);positions.push(p.x,p.y,p.z);}}
 const col=rgb(threshold,q.palette);
 const geometry=new Cesium.Geometry({attributes:{position:new Cesium.GeometryAttribute({componentDatatype:Cesium.ComponentDatatype.DOUBLE,
   componentsPerAttribute:3,values:new Float64Array(positions)})},indices:new Uint32Array(idx),primitiveType:Cesium.PrimitiveType.TRIANGLES,
   boundingSphere:Cesium.BoundingSphere.fromVertices(positions)});
 const instance=new Cesium.GeometryInstance({geometry,attributes:{color:Cesium.ColorGeometryInstanceAttribute.fromColor(
   new Cesium.Color(col[0]/255,col[1]/255,col[2]/255,.30+q.opacity*.35))}});
 q.ownPrimitives.push(q.viewer.scene.primitives.add(new Cesium.Primitive({geometryInstances:instance,
   appearance:new Cesium.PerInstanceColorAppearance({flat:true,translucent:true,closed:false}),asynchronous:false,allowPicking:false})));
 q.lastSurfaceN=result.triangles.length;
 $('renderInfo').textContent=`等値面 ${result.triangles.length} triangles${result.truncated?' (上限)' : ''} | 閾値 10^${fmt(threshold,1)} m⁻³`;
}
function safeRender(){try{render();}catch(e){console.error(e);status('3D表示の計算エラー: '+e.message+'\n単一高度モードに切り替えるか、描画密度を下げてください。')}}
function render(){
 if(!q.data||!q.viewer)return;
 const f=frame();if(!f)throw Error('選択時刻のIRIモデルデータがありません');
 const ss=sites();if(ss.length<4)throw Error('IRI実計算地点が4件未満です。別の時刻または全球へ切替えてください。');
 clearGraphics();q.lastSurfaceN=0;
 if(['single','section','fof2','hmf2'].includes(q.mode))addTextureShell(q.mode==='fof2'?300:q.mode==='hmf2'?350:q.alt,`${q.mode} / model surface`,false);
 if(q.mode==='multi'){
   const layers=activeLayers();if(!layers.length)throw Error('表示層を少なくとも1つ選択してください');
   for(const layer of layers)addTextureShell(layer.height,layer.id,true,layer.id);
 }
 if(q.mode==='iso')buildIsosurface();
 if(q.mode==='voxel')buildVoxels();
 if(q.mode==='section')drawRouteLines(true);
 else drawRouteLines(false);
 if(['single','section','fof2','hmf2'].includes(q.mode))addModelSiteDots();
 $('nSites').textContent=ss.length;
 $('nCells').textContent=q.lastSurfaceN.toLocaleString('ja-JP');
 $('nLevels').textContent=q.mode==='multi'?activeLayers().length:q.mode==='voxel'?6:1;
 $('frameTime').textContent=DATE_FORMAT.format(new Date(f.valid_at));
 const type=isForecast()?(q.modelVariant==='tec'?'TEC-linked EXPLORATORY SCENARIO':'future IRI CLIMATOLOGY'):
   q.source==='japan'?'ISEE VTEC observation at matching IRI UTC':'IRI reference climatology';
 $('viewSub').textContent=`${type} · ${f.valid_at}`;
 $('overlayTitle').textContent=`${q.mode==='multi'?'E / F1 / F2 / TOPSIDE • ':''}${f.valid_at} UTC | ${type} | ${isFuture()?'FUTURE-VALID':'REPLAY / REFERENCE'}`;
 if(['single','multi','section','fof2','hmf2'].includes(q.mode))$('renderInfo').textContent=`${q.lastSurfaceN.toLocaleString('ja-JP')} texture pixels | 固定カラースケール`;
 if(['fof2','hmf2'].includes(q.mode)){
   $('renderInfo').textContent=q.mode==='fof2'?'foF2 [MHz] · scale 1–18 MHz':'hmF2 [km] · scale 150–550 km';
   $('ramp').setAttribute('aria-label', $('renderInfo').textContent);
 }
 q.viewer.scene.requestRender();
 showSelection();drawSection();drawProfile();drawIseeMap();updateMetadata();
 status(`${f.valid_at} UTC | ${type} | ${isFuture()?'発表後の将来時刻':'参考・再生データ'}
`+
   `IRI鉛直密度の時間・空間補間。TEC倍率補正は条件付きの研究シナリオで、予報精度未検証。`);
}
function canvas(el){const c=$(el),d=Math.min(2,window.devicePixelRatio||1),w=Math.max(250,c.clientWidth||400),h=Math.max(160,c.clientHeight||240);
 if(c.width!==Math.round(w*d)||c.height!==Math.round(h*d)){c.width=Math.round(w*d);c.height=Math.round(h*d)}
 const ctx=c.getContext('2d');ctx.setTransform(d,0,0,d,0,0);return{ctx,w,h};}
function background(ctx,w,h){ctx.fillStyle='#091d2e';ctx.fillRect(0,0,w,h);}
function drawSection(){
 if(!q.data)return;const{ctx,w,h}=canvas('sectionCanvas');background(ctx,w,h);
 const ss=sites();if(!ss.length)return;
 const route=q.routePoints,alts=heights();if(route.length<2)return;
 const l=58,r=w-12,t=16,b=h-38,N=route.length,steps=40;
 const weights=route.map(p=>weightsFor(ss,p.lat,p.lon));
 for(let i=0;i<N;i++)for(let j=0;j<steps;j++){
   const alt=100+(j+.5)*900/steps,v=neAt(ss,weights[i],alt,alts),c=rgba(v,q.palette,1);
   ctx.fillStyle=valid(v)?`rgb(${c[0]},${c[1]},${c[2]})`:'#142d3c';
   ctx.fillRect(l+i*(r-l)/N,b-(j+1)*(b-t)/steps,(r-l)/N+1,(b-t)/steps+1);
 }
 ctx.strokeStyle='#557185';ctx.lineWidth=.8;ctx.font='11px system-ui';ctx.textBaseline='middle';
 for(const km of [100,200,300,400,600,800,1000]){
   const y=b-(km-100)/900*(b-t);ctx.beginPath();ctx.moveTo(l,y);ctx.lineTo(r,y);ctx.stroke();ctx.fillStyle='#b6d6e7';ctx.fillText(km+' km',4,y);
 }
 ctx.fillStyle='#c9e7f3';ctx.fillText('0 km',l,b+16);ctx.textAlign='right';ctx.fillText(fmt(route.at(-1).km,0)+' km',r,b+16);ctx.textAlign='left';
 if(sourceClass()==='japan'&&weights.filter(x=>!x.length).length)ctx.fillText('日本域外はモデル補間欠測',l,t+12);
 $('sectionTitle').textContent=`${q.mode==='section'?'3D Curtain · ':'垂直断面 · '} ${fmt(route.at(-1).km,0)} km / 100〜1000 km`;
}
function nearestSiteAt(lat,lon){
 const ss=sites();if(!ss.length)return null;
 let best=ss[0],d=Infinity;for(const s of ss){const n=distanceKm(lat,lon,s.lat,s.lon);if(n<d){d=n;best=s}}
 return {site:best,km:d};
}
function showSelection(){
 const s=nearestSiteAt(...q.selected);if(!s)return;
 $('pickedLoc').textContent=`${fmt(q.selected[0])}°, ${fmt(q.selected[1])}°`;
 const arr=s.site.ne_log10_m3?.filter(valid)||[];
 const max=arr.length?Math.max(...arr):null;
 $('pickedPeak').textContent=valid(max)?Math.pow(10,max).toExponential(2):'—';
 $('pickedDetails').textContent=`選択位置に最も近いIRI計算点: ${fmt(s.site.lat,2)}°, ${fmt(s.site.lon,2)}°（約${fmt(s.km,0)} km）。foF2 ${fmt(characteristic(s.site,'fof2'),2)} MHz / hmF2 ${fmt(characteristic(s.site,'hmf2'),0)} km。IRI基準・研究シナリオであり、直接観測ではありません。`;
}
function drawProfile(){
 if(!q.data)return;const{ctx,w,h}=canvas('profileCanvas');background(ctx,w,h);
 const n=nearestSiteAt(...q.selected);if(!n)return;
 const values=n.site.ne_log10_m3||[],alts=heights(),l=44,r=w-15,t=20,b=h-36;
 ctx.lineWidth=.8;ctx.strokeStyle='#416079';
 for(let p=8;p<=13;p++){const x=l+(p-8)/5*(r-l);ctx.beginPath();ctx.moveTo(x,t);ctx.lineTo(x,b);ctx.stroke();ctx.fillStyle='#a7c8dc';ctx.font='10px system-ui';ctx.fillText(String(p),x-6,b+16)}
 for(const alt of [100,300,500,700,900]){const y=b-(alt-100)/900*(b-t);ctx.beginPath();ctx.moveTo(l,y);ctx.lineTo(r,y);ctx.stroke();ctx.fillStyle='#b5d5e6';ctx.fillText(alt+' km',3,y+3)}
 ctx.lineWidth=2.6;ctx.strokeStyle='#65e1ef';ctx.beginPath();let started=false;
 for(let i=0;i<alts.length;i++){
   const v=values[i];if(!valid(v)){started=false;continue}
   const x=l+clamp((v-8)/5,0,1)*(r-l),y=b-(alts[i]-100)/900*(b-t);
   if(started)ctx.lineTo(x,y);else ctx.moveTo(x,y);started=true;
 }
 ctx.stroke();ctx.fillStyle='#d1eaf7';ctx.fillText('log₁₀ Ne [m⁻³]',Math.max(l,r-112),14);
}
function drawIseeMap(){
 if(!q.data)return;const {ctx,w,h}=canvas('iseeMap');background(ctx,w,h);
 const g=sourceClass()==='japan'?frame()?.vtec:null;
 if(!g?.lat_arr?.length||!g?.lon_arr?.length){ctx.fillStyle='#b7cede';ctx.font='12px system-ui';ctx.fillText('全球モード：ISEE VTECの表示なし',10,28);$('iseeMeta').textContent='日本モードの同時刻データを選択するとISEE VTECを表示します。';return}
 const lat=g.lat_arr,lon=g.lon_arr,x0=12,y0=11,ww=w-24,hh=h-22,nx=lon.length,ny=lat.length;
 for(let i=0;i<ny;i++)for(let j=0;j<nx;j++){
   const v=g.grid_tecu[i]?.[j],f=clamp((v??0)/80,0,1),col=rgb(LOG_MIN+f*(LOG_MAX-LOG_MIN),'thermal');
   ctx.fillStyle=valid(v)?`rgb(${col.join(',')})`:'#0b1d2f';ctx.fillRect(x0+j*ww/nx,y0+(ny-i-1)*hh/ny,ww/nx+1,hh/ny+1);
 }
 const x=x0+(q.selected[1]-lon[0])/(lon.at(-1)-lon[0])*ww,y=y0+(lat.at(-1)-q.selected[0])/(lat.at(-1)-lat[0])*hh;
 if(x>=x0&&x<=x0+ww&&y>=y0&&y<=y0+hh){ctx.strokeStyle='white';ctx.lineWidth=2;ctx.beginPath();ctx.arc(x,y,5,0,7);ctx.stroke();}
 $('iseeMeta').textContent=`ISEE AGRID2 VTEC [TECU] | ${frame()?.valid_at} UTC | 元資料: ${g.source_file||'—'} | 観測遅延: ${fmt(frame()?.source_age_hours)}h。これは電子密度の3D実測ではありません。`;
}
function updateMetadata(){
 const f=frame(),j=q.data.japan||{};
 if(isForecast()){
  const eligible=f.sites?.filter(s=>valid(s.factor)).length||0;
  $('sourceMeta').textContent=`30-min VTEC + IRI forward climatology: ${f.valid_at} UTC | ${eligible}/${f.sites?.length||0} TEC-linked eligible sites | issued ${q.forecast.metadata.issued_at}`;
  $('sourceNote').textContent=`${f.is_prospective?'将来時刻の推定':'発表時刻以前の参考再生'}。${q.modelVariant==='tec'?'TEC一様倍率シナリオ。予報技能は未検証。':'将来時刻のIRI気候モデル。'} 時間補間 ${q.forecast.metadata.iri_anchor_hours}時間間隔。`;
 }else{
  $('sourceMeta').textContent=q.source==='japan'?`ISEE観測 UTC: ${f.valid_at} | source age ${fmt(f.source_age_hours)} h | ${j.source_product||'ISEE VTEC'} | IRI計算点 ${sites().length}`:
    `IRI-2020 climatology valid at ${f.valid_at} (not independently validated future forecast)`;
  $('sourceNote').textContent=q.source==='japan'?`ISEE配信遅延 ${fmt(f.source_age_hours)}h。観測VTECに合わせIRIを同一UTCで計算。`:'全球IRIモデル（ISEEと観測時刻は異なります）。';
 }
 $('modelVariant').disabled=!isForecast();
 $('timeCounter').textContent=`${q.frame+1} / ${frames().length} · ${f.valid_at} UTC`;
 $('seek').max=String(Math.max(0,frames().length-1));$('seek').value=String(q.frame);
 if($('fsSeek')){$('fsSeek').max=$('seek').max;$('fsSeek').value=String(q.frame);$('fsTime').textContent=frames()[q.frame]?.valid_at||'— UTC';$('fsPlay').textContent=q.timer?'⏸ 停止':'▶ 再生';}
 $('altValue').textContent=q.alt+' km';$('opacityValue').textContent=Math.round(q.opacity*100)+'%';
 $('isoValue').textContent=Number($('iso').value).toFixed(2);
}

function redraw(){if(!q.data)return;safeRender()}
function stop(){if(q.timer){clearInterval(q.timer);q.timer=null;}$('play').textContent='▶ 再生';}
function step(delta){if(!frames().length)return;q.frame=(q.frame+delta+frames().length)%frames().length;q.weightCache.clear();$('frame').value=String(q.frame);redraw()}
function setSource(source){
 stop();
 if(source==='japan'&&!q.data.japan?.frames?.some(f=>f.iri_sites?.length>=4)){
  status('日本ISEE＋IRIデータがありません。全球IRIで代替します。');source='global';
 }
 if(source.startsWith('forecast-')&&(!q.forecast?.frames?.length||q.forecast.status==='MODEL_UNAVAILABLE'||q.forecast.status==='IRI_UNAVAILABLE')){
  status('30分 IRI+TEC予報がありません。従来の全球IRIに切り替えます。');source='global';
 }
 if(source==='forecast-japan'){
  const regional=q.forecast?.frames?.[0]?.sites?.filter(s=>s.lat>=23&&s.lat<=47&&s.lon>=121&&s.lon<=152)||[];
  if(regional.length<4){status('日本域予報地点が4件未満です。全球予報に切り替えます。');source='forecast-global'}
 }
 q.source=source;q.frame=0;q.weightCache.clear();$('source').value=source;
 $('frame').replaceChildren(...frames().map((f,i)=>new Option(f.valid_at+' UTC'+(f.is_prospective===false?' (reference)':''),String(i))));
 q.selected=sourceClass()==='japan'?[35.68,139.76]:[20,120];q.routePoints=routeSamples(q.route,72);
 cameraToData();safeRender();
}

function applyRoute(){try{
 q.route=parseRoute($('route').value);q.routePoints=routeSamples(q.route,72);
 setMode('section');
}catch(e){status('経路の形式エラー: '+e.message)}}
function installControls(){
 const layers=$('layerSwitches');layers.replaceChildren();
 for(const x of HEIGHT_LAYERS){
   const div=document.createElement('div');div.className='layer';
   const lab=document.createElement('label');const check=document.createElement('input');check.type='checkbox';check.id='layer-'+x.id;check.checked=true;
   const dot=document.createElement('span');dot.className='swatch';dot.style.background=x.color;dot.style.color=x.color;
   lab.append(check,dot,document.createTextNode(x.id+' · '+x.height+' km'));
   const sub=document.createElement('input');sub.type='range';sub.id='layerAlpha-'+x.id;sub.min='10';sub.max='100';sub.step='5';sub.value='65';sub.title=x.id+'の個別透明度';sub.setAttribute('aria-label',x.id+'の個別透明度');div.append(lab,sub);layers.append(div);sub.addEventListener('change',()=>{if(q.mode==='multi')redraw()});
   check.addEventListener('change',()=>{if(q.mode==='multi')redraw()});
 }
 document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>setMode(b.dataset.mode)));
 $('source').addEventListener('change',e=>setSource(e.target.value));
 $('frame').addEventListener('change',e=>{q.frame=Number(e.target.value);q.weightCache.clear();redraw()});
 $('prev').addEventListener('click',()=>{stop();step(-1)});$('next').addEventListener('click',()=>{stop();step(1)});
 function startPlayback(){stop();if(frames().length<2)return;$('play').textContent='⏸ 停止';
   q.timer=setInterval(()=>step(1),1000/Number($('speed').value));}
 $('play').addEventListener('click',()=>{if(q.timer)stop();else startPlayback()});
 $('speed').addEventListener('change',()=>{if(q.timer)startPlayback()});
 $('seek').addEventListener('input',e=>{stop();q.frame=Math.min(frames().length-1,Math.max(0,Number(e.target.value)||0));q.weightCache.clear();$('frame').value=String(q.frame);redraw()});
 for(const [fs,base] of [['fsPrev','prev'],['fsPlay','play'],['fsNext','next']])$(fs)?.addEventListener('click',()=>$(base).click());
 $('fsSeek')?.addEventListener('input',e=>{$('seek').value=e.target.value;$('seek').dispatchEvent(new Event('input',{bubbles:true}))});
 $('fsExit')?.addEventListener('click',()=>{if(document.fullscreenElement)document.exitFullscreen()});
 $('modelVariant').addEventListener('change',e=>{q.modelVariant=e.target.value;q.weightCache.clear();redraw()});
 $('basemap').addEventListener('change',applyBasemap);
 $('scene3d').addEventListener('click',()=>projection('3d'));
 $('scene2d').addEventListener('click',()=>projection('2d'));
 $('scene25d').addEventListener('click',()=>projection('25d'));
 $('sidePreset').addEventListener('click',()=>cameraPreset('side'));
 $('topPreset').addEventListener('click',()=>cameraPreset('top'));
 for(const [id,label] of [['cameraPitch','cameraPitchValue'],['cameraHeading','cameraHeadingValue'],['cameraRange','cameraRangeValue']]){
  $(id).addEventListener('input',e=>$(label).textContent=e.target.value+(id==='cameraRange'?' km':'°'));
  $(id).addEventListener('change',applyCameraPose);
 }
 $('fullscreen').addEventListener('click',async()=>{
   const target=document.querySelector('.workspace');try{
    if(document.fullscreenElement){await document.exitFullscreen()}else await target.requestFullscreen();
   }catch(e){status('全画面表示に失敗: '+e.message)}
 });
 document.addEventListener('fullscreenchange',()=>{ $('fullscreen').textContent=document.fullscreenElement?'⤢ 全画面を終了':'⛶ 3D画面＋断面を全画面表示';
   setTimeout(()=>{q.viewer?.resize();drawSection();drawProfile();},100);
 });
 $('alt').addEventListener('input',e=>{q.alt=Number(e.target.value);$('altValue').textContent=q.alt+' km'});
 $('alt').addEventListener('change',()=>{if(q.mode==='single'||q.mode==='section')redraw()});
 $('palette').addEventListener('change',e=>{q.palette=e.target.value;updateRamp();redraw()});
 $('opacity').addEventListener('input',e=>{$('opacityValue').textContent=e.target.value+'%'});
 $('opacity').addEventListener('change',e=>{q.opacity=Number(e.target.value)/100;redraw()});
 $('resolution').addEventListener('change',redraw);
 $('iso').addEventListener('input',e=>$('isoValue').textContent=Number(e.target.value).toFixed(2));
 $('iso').addEventListener('change',()=>{if(q.mode==='iso'||q.mode==='voxel')redraw()});
 $('voxelLimit').addEventListener('change',()=>{if(q.mode==='iso'||q.mode==='voxel')redraw()});
 $('routePreset').addEventListener('change',e=>{const val=ROUTES[e.target.value];if(val){$('route').value=val.map(p=>p.join(', ')).join('\n')}});
 $('applyRoute').addEventListener('click',applyRoute);
 $('focus').addEventListener('click',cameraToData);
 $('city').addEventListener('change',e=>{q.selected=e.target.value.split(',').map(Number);showSelection();drawProfile();drawIseeMap()});
 window.addEventListener('resize',()=>{clearTimeout(q.resizeTimer);q.resizeTimer=setTimeout(()=>{drawSection();drawProfile();drawIseeMap();q.viewer?.resize()},160)});
 updateRamp();
}
function updateRamp(){const pal=PALETTES[q.palette]||PALETTES.turbo;$('ramp').style.background='linear-gradient(90deg,'+pal.map(c=>'rgb('+c.join(',')+')').join(',')+')';}
async function init(){
 installControls();q.routePoints=routeSamples(q.route,72);
 try{
  const r=await fetch('./explorer_data.json',{cache:'no-store'});
  if(!r.ok)throw Error('explorer_data.json HTTP '+r.status);
  const data=await r.json();
  if(data.schema!=='swift-ion-explorer-v1.4'||!Array.isArray(data.global_frames)||!data.global_frames.length)throw Error('IRI Explorerデータ形式が不正');
  q.data=data;
  try{
   const x=await fetch('./ion_forecast.json',{cache:'no-store'});
   if(x.ok){const t=await x.json();if(t.schema==='swift-ion-iri-tec-forecast-v1'&&t.frames?.length&&t.status!=='MODEL_UNAVAILABLE'&&t.status!=='IRI_UNAVAILABLE')q.forecast=t;
    else console.warn('Forecast unavailable',t.status);}
  }catch(e){console.warn('Optional 30-minute IRI forecast unavailable:',e.message)}
  createViewer();
  const haveJapan=data.japan?.frames?.some(f=>f.iri_sites?.length>=4);
  setSource(q.forecast?.frames?.length?'forecast-japan':haveJapan?'japan':'global');
  if(!q.forecast?.frames?.length)status('30分 IRI + TEC 予報の公開待ち。従来のIRI画面は使用可能です。');
 }catch(e){console.error(e);status('Explorer起動失敗: '+e.message+'。ActionsのExplorerステップを確認してください。')}
}

window.addEventListener('pagehide',stop);
init();
