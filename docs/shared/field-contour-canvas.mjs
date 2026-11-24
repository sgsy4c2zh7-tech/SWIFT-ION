/** Canvas contours from the same scalar grid used by the SWIFT-ION heatmap.
 * Invalid four-corner cells are skipped. No interpolation across missing data.
 */
export function segmentsForLevel(grid, values, level) {
  const { latitudes, longitudes, nx, ny } = grid || {};
  if (!Array.isArray(values) || values.length !== nx * ny || nx < 2 || ny < 2) return [];
  const out = [];
  for (let i = 0; i < ny - 1; i++) for (let j = 0; j < (grid.regional ? nx - 1 : nx); j++) {
    const j2 = (j + 1) % nx;
    const a = i * nx, b = (i + 1) * nx;
    const v = [values[a+j], values[a+j2], values[b+j2], values[b+j]];
    if (v.some(x => x === null || !Number.isFinite(x))) continue;
    const x1 = longitudes[j], x2 = j2 === 0 ? longitudes[0] + 360 : longitudes[j2];
    const pt = [[x1,latitudes[i]], [x2,latitudes[i]], [x2,latitudes[i+1]], [x1,latitudes[i+1]]];
    const crosses = [];
    for (let edge = 0; edge < 4; edge++) {
      const next = (edge + 1) % 4;
      if ((v[edge] < level) === (v[next] < level)) continue;
      const t = Math.max(0, Math.min(1, (level-v[edge])/(v[next]-v[edge])));
      crosses.push({edge, pt: [pt[edge][0]+t*(pt[next][0]-pt[edge][0]),pt[edge][1]+t*(pt[next][1]-pt[edge][1])]});
    }
    if (crosses.length === 2) out.push([crosses[0].pt, crosses[1].pt]);
    if (crosses.length === 4) {
      // Asymptotic-like centre-value rule, stable for cells with a saddle.
      const centre = (v[0]+v[1]+v[2]+v[3])/4;
      if ((v[0] >= level) === (centre >= level)) {
        out.push([crosses[0].pt,crosses[1].pt],[crosses[2].pt,crosses[3].pt]);
      } else {
        out.push([crosses[0].pt,crosses[3].pt],[crosses[1].pt,crosses[2].pt]);
      }
    }
  }
  return out;
}

/** Draw 1 chosen frame's isolines + labels, optionally sparse numeric grid labels. */
export function drawContours(canvas, map, grid, values, step=2, unit='m',
  {showLines=true, showLabels=true, showNumbers=false}={}) {
  const size=map.getSize(), dpr=Math.min(2,window.devicePixelRatio||1), w=size.x, h=size.y;
  if (w < 2 || h < 2) return;
  canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
  if (!grid || !values?.length || !(step>0)) return;
  const good=values.filter(x=>x!==null&&Number.isFinite(x));if (!good.length)return;
  const taken=[];
  const numberFormat=x=>Math.abs(x)>=100?x.toFixed(0):x.toFixed(1);
  if (showLines) {
    const lo=Math.min(...good), hi=Math.max(...good);
    const loN=Math.ceil(lo/step), hiN=Math.floor(hi/step), stride=Math.max(1,Math.ceil((hiN-loN+1)/85));
    ctx.lineJoin='round';ctx.lineCap='round';
    for (let k=loN;k<=hiN;k+=stride) {
      const level=+(k*step).toFixed(5), segs=segmentsForLevel(grid,values,level);
      if (!segs.length)continue;
      const major=k%2===0;
      ctx.lineWidth=major?2.05:1.05;
      ctx.strokeStyle=major?'rgba(255,255,255,.94)':'rgba(255,255,255,.65)';
      ctx.beginPath();
      const candidates=[];
      for (const [a,b] of segs) {
        for (let world=-2;world<=2;world++) {
          const p=map.latLngToContainerPoint([a[1],a[0]+world*360]);
          const q=map.latLngToContainerPoint([b[1],b[0]+world*360]);
          if (Math.max(p.x,q.x)<0||Math.min(p.x,q.x)>w||Math.max(p.y,q.y)<0||Math.min(p.y,q.y)>h)continue;
          ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);
          if (major && candidates.length<80 && Math.hypot(q.x-p.x,q.y-p.y)>5)
            candidates.push([(p.x+q.x)/2,(p.y+q.y)/2]);
        }
      }
      ctx.stroke();
      if (major && showLabels) {
        ctx.font='bold 11px system-ui,sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';
        for (const [x,y] of candidates) {
          if (x<28||x>w-28||y<75||y>h-85)continue;
          if (taken.some(p=>(p[0]-x)**2+(p[1]-y)**2<100**2))continue;
          taken.push([x,y]);
          const label=`${numberFormat(level)} ${unit}`;
          ctx.lineWidth=3.5;ctx.strokeStyle='rgba(1,15,27,.98)';ctx.strokeText(label,x,y);
          ctx.fillStyle='white';ctx.fillText(label,x,y);
        }
      }
    }
  }
  if (showNumbers) {
    const cols=grid.nx, rows=grid.ny;
    const strideX=Math.max(1,Math.round(cols/18)),strideY=Math.max(1,Math.round(rows/10));
    ctx.font='bold 11px system-ui,sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';
    for (let i=0;i<rows;i+=strideY)for(let j=0;j<cols;j+=strideX){
      const val=values[i*cols+j];if(val===null||!Number.isFinite(val))continue;
      const lat=grid.latitudes[i],lon=grid.longitudes[j];
      for(let world=-2;world<=2;world++){
        const p=map.latLngToContainerPoint([lat,lon+world*360]);
        if(p.x<28||p.x>w-28||p.y<90||p.y>h-90)continue;
        if(taken.some(q=>(q[0]-p.x)**2+(q[1]-p.y)**2<68**2))continue;
        taken.push([p.x,p.y]);
        const label=numberFormat(val);ctx.lineWidth=3.2;ctx.strokeStyle='#0b2135';ctx.strokeText(label,p.x,p.y);
        ctx.fillStyle='#f7fbff';ctx.fillText(label,p.x,p.y);
      }
    }
  }
}
