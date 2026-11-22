/** SWIFT-ION display-only foF2 view period and defensible missing-data clues.
 * The upstream SWIFT-TEC animation is 241 frames (120h); the preferred
 * 24h prior-side + 72h forecast view uses its first 96 hours. This view
 * does NOT change model frames, issue timestamps, or 365-day skill history.
 */
export const PREVIOUS_SIDE_MS = 24 * 3600_000;
export const FORECAST_3DAY_MS = 72 * 3600_000;
export const DISPLAY_MS = PREVIOUS_SIDE_MS + FORECAST_3DAY_MS;

export function windowFromForecast(frames, mode='swifttec96') {
  if (!Array.isArray(frames) || !frames.length) throw Error('Forecast frames unavailable');
  const ts = frames.map(f => Date.parse(f.valid_at));
  if (ts.some(t => !Number.isFinite(t)) || ts.some((t,i) => i > 0 && t <= ts[i-1])) {
    throw Error('Forecast UTC timestamps invalid or not strictly increasing');
  }
  const first = ts[0], last = ts[ts.length - 1];
  if (mode === 'all') return {min:first,max:last,description:'全モデル時刻（参考）',referenceEnd:null};
  if (mode === 'swifttec96') return {
    min:first,
    max:Math.min(last,first+DISPLAY_MS),
    referenceEnd:Math.min(last,first+PREVIOUS_SIDE_MS),
    description:'SWIFT-TEC前日側24時間＋続く3日間（最大96時間）'
  };
  const hours = Number(mode);
  if (hours === 48 || hours === 96) return {
    min:Math.max(first,last-hours*3600_000),max:last,
    referenceEnd:null,description:`末尾${hours}時間（参考）`
  };
  throw Error('Unsupported display window: '+mode);
}

const STATUS_LABELS = Object.freeze({
  VTEC_PARTIAL_TEC_MISMATCH:'VTECとIRI部分TECの比が許容範囲外',
  TOPSIDE_TRUNCATION:'IRIの高度上端が十分に収束していない',
  VTEC_MISSING:'VTEC欠測・IRI部分TEC不成立',
  IRI_PEAK_UNAVAILABLE:'IRIのF2ピーク推定不可',
  SCENARIO_AVAILABLE:'周辺値の欠落／空間補間の制約',
  NO_MODEL_SITE:'近傍計算点なし',
  UNKNOWN:'未分類'
});
function sphereDistanceKm(lat,lon,clat,clon) {
  const a=lat*Math.PI/180,b=clat*Math.PI/180;
  const cos=Math.sin(a)*Math.sin(b)+Math.cos(a)*Math.cos(b)*Math.cos((lon-clon)*Math.PI/180);
  return 6371*Math.acos(Math.max(-1,Math.min(1,cos)));
}

/** Returns descriptive *nearest model site* reasons for missing station series.
 * Never claim a single nearest-site code is the exact IDW station failure.
 * forecastRows must contain already sampled station values for the SAME view.
 */
export function missingClues(frames, forecastRows, station, bounds) {
  const byTime = new Map(frames.map(f => [Date.parse(f.valid_at),f]));
  const counts = {};
  let total=0, valid=0, missing=0;
  for (const row of forecastRows) {
    if (row.station !== station.id || row.ms<bounds.min || row.ms>bounds.max) continue;
    total++;
    if (Number.isFinite(row.model_mhz)) { valid++; continue; }
    missing++;
    const f=byTime.get(row.ms);
    let status='NO_MODEL_SITE', nearest=Infinity;
    for (const site of (f?.sites||[])) {
      if (!Number.isFinite(site.lat)||!Number.isFinite(site.lon)) continue;
      const d=sphereDistanceKm(station.lat,station.lon,site.lat,site.lon);
      if(d<nearest){nearest=d;status=site.scenario_status||'UNKNOWN';}
    }
    if (!(status in STATUS_LABELS)) status='UNKNOWN';
    counts[status]=(counts[status]||0)+1;
  }
  return {total,valid,missing,counts,
    breakdown:Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(([code,count])=>({code,count,label:STATUS_LABELS[code]}))};
}
