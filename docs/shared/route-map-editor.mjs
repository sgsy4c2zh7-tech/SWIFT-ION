/** SWIFT-ION route editing: public/hypothetical research routes only.
 * Leaflet map taps add points in explicit Add mode; drag existing markers in any mode;
 * click a provisional route segment to insert an intermediate waypoint.
 * Visual map movement (pan/zoom) remains available in View mode.
 */
export const MAX_WAYPOINTS=12;
export function validatePoints(points,{allowPartial=false}={}){
  if(!Array.isArray(points)||points.length>MAX_WAYPOINTS||(!allowPartial&&points.length<2))
    throw Error(`経由点は${allowPartial?'0〜':'2〜'}${MAX_WAYPOINTS}地点にしてください`);
  return points.map((p,i)=>{
    if(!Array.isArray(p)||p.length!==2||p.some(x=>!Number.isFinite(Number(x))))throw Error(`${i+1}番目の座標が不正です`);
    const v=p.map(Number);if(Math.abs(v[0])>90||Math.abs(v[1])>180)throw Error(`${i+1}番目が座標範囲外です`);
    return v;
  });
}
export function parsePoints(text,{allowPartial=false}={}){
  const lines=String(text||'').trim().split(/\n+/).map(s=>s.trim()).filter(Boolean);
  if(!lines.length&&allowPartial)return [];
  return validatePoints(lines.map((s,i)=>{
    const arr=s.split(/[,，\s]+/).filter(Boolean);
    if(arr.length!==2||arr.some(x=>x===''))throw Error(`${i+1}行目は「緯度, 経度」にしてください`);
    return arr.map(Number);
  }),{allowPartial});
}
export function pointsText(points){return validatePoints(points,{allowPartial:true}).map(p=>p.map(x=>Number(x).toFixed(5)).join(', ')).join('\n')}
/** Nearest segment in 2-D projected pixels, for users who tap the edit line. */
export function closestSegment(points,x,y){
  if(points.length<2)return -1;
  let best=-1,dist=Infinity;
  for(let i=0;i<points.length-1;i++){
    const [ax,ay]=points[i],[bx,by]=points[i+1],dx=bx-ax,dy=by-ay;
    const t=Math.max(0,Math.min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy||1)));
    const d=(x-(ax+t*dx))**2+(y-(ay+t*dy))**2;
    if(d<dist){dist=d;best=i}
  }
  return best;
}
export function insertAfter(points,index,point){
  const copy=validatePoints(points,{allowPartial:true});
  if(copy.length>=MAX_WAYPOINTS)throw Error('経由点は最大12地点です');
  if(!Number.isInteger(index)||index< -1||index>=copy.length)throw Error('挿入位置が不正です');
  copy.splice(index+1,0,point);
  return validatePoints(copy,{allowPartial:true});
}

/** @param {object} args {map, points, onChange, listElement, onMessage} */
export function createRouteMapEditor({map,points=[],onChange=()=>{},listElement=null,onMessage=()=>{}}){
  if(!map||!globalThis.L)throw Error('Leaflet map が必要です');
  const L=globalThis.L;
  let coords=validatePoints(points,{allowPartial:true}), mode='view';
  let line=null,markers=[],waypointsAdded=0;
  const markerIcon=i=>L.divIcon({className:'swift-route-marker',html:`<span>${i+1}</span>`,iconSize:[29,29],iconAnchor:[14,14]});
  function notify(){onChange(coords.map(p=>p.slice()));}
  function draw(){
    if(line)map.removeLayer(line);
    for(const marker of markers)map.removeLayer(marker);
    markers=[];
    if(coords.length>=2){
      line=L.polyline(coords.map(p=>[p[0],p[1]]),{color:'#ffca75',weight:4,opacity:.85,dashArray:'7,5',bubblingMouseEvents:false}).addTo(map);
      line.on('click',e=>{
        if(mode!=='insert')return;
        if(coords.length>=MAX_WAYPOINTS){onMessage('最大12地点までです');return}
        const projected=coords.map(p=>{
          const pt=map.latLngToContainerPoint(L.latLng(p[0],p[1]));return [pt.x,pt.y]
        });
        const target=map.latLngToContainerPoint(e.latlng),index=closestSegment(projected,target.x,target.y);
        coords=insertAfter(coords,index,[e.latlng.lat,e.latlng.lng]);notify();draw();
      });
    }
    coords.forEach((p,i)=>{
      const mk=L.marker([p[0],p[1]],{draggable:true,autoPan:true,icon:markerIcon(i),keyboard:true,bubblingMouseEvents:false,title:`地点${i+1}：ドラッグで位置変更`}).addTo(map);
      mk.on('dragend',()=>{
        const pos=mk.getLatLng();coords[i]=[Number(pos.lat.toFixed(5)),Number(pos.lng.toFixed(5))];
        notify();draw();
      });
      markers.push(mk);
    });
    if(listElement){
      listElement.replaceChildren();
      coords.forEach(([lat,lon],i)=>{
        const row=document.createElement('div');row.className='swift-waypoint-item';
        const label=document.createElement('span');label.textContent=`${i+1}. ${lat.toFixed(3)}°, ${lon.toFixed(3)}°`;row.append(label);
        const move=(name,delta)=>{
          const b=document.createElement('button');b.type='button';b.textContent=name;b.title=`地点${i+1}を${delta<0?'前':'後'}に移動`;b.disabled=i+delta<0||i+delta>=coords.length;
          b.addEventListener('click',()=>{[coords[i],coords[i+delta]]=[coords[i+delta],coords[i]];notify();draw();});row.append(b);
        };
        move('↑',-1);move('↓',1);
        const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.title=`地点${i+1}を削除`;
        remove.addEventListener('click',()=>{coords.splice(i,1);notify();draw()});row.append(remove);
        listElement.append(row);
      });
    }
  }
  function clickMap(e){
    if(mode!=='add')return;
    if(coords.length>=MAX_WAYPOINTS){onMessage('最大12地点です。地点を削除するかドラッグで修正してね');return}
    coords.push([Number(e.latlng.lat.toFixed(5)),Number(e.latlng.lng.toFixed(5))]);waypointsAdded++;notify();draw();
  }
  map.on('click',clickMap);
  function setPoints(next,{silent=false,fit=false}={}){
    coords=validatePoints(next,{allowPartial:true});draw();if(!silent)notify();
    if(fit&&coords.length>=2)map.fitBounds(L.latLngBounds(coords.map(p=>[p[0],p[1]])).pad(.14),{maxZoom:7});
  }
  function setMode(next){if(!['view','add','insert'].includes(next))throw Error('Unknown route edit mode');mode=next;const c=map.getContainer();c.classList.toggle('swift-add-mode',mode==='add');onMessage(mode==='view'?'地図移動モード：通常操作でスクロール、ピンはドラッグで編集できます':mode==='add'?'追加モード：地図をタップして経由点を追加。ドラッグで地図の移動もできます':'挿入モード：経路の線をタップして途中へ経由点を追加');}
  draw();
  return {getPoints:()=>coords.map(p=>p.slice()),setPoints,setMode,getMode:()=>mode,clear:()=>setPoints([]),dispose:()=>{map.off('click',clickMap);if(line)map.removeLayer(line);for(const mk of markers)map.removeLayer(mk);},getStats:()=>({count:coords.length,addedByTap:waypointsAdded})};
}
