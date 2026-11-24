"""Export the *actual* original SWIFT-TEC/ISEE Japan 30-minute VTEC forecast.

The Japanese forecast is computed by the upstream swiftIseeRunMeanForecast;
this bridge supplies the same-issue, verified NOAA Kp slots already used in
SWIFT-TEC's global run. It NEVER substitutes global VTEC or historical ISEE
observations for the ISEE-based Japan forecast.
"""
from __future__ import annotations
import json, os, sys, threading
from datetime import datetime, timezone
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from animation_format import create_animation, check_animation
from japan_kp_issue import verified_slots

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / '_upstream_swifttec' / 'docs'
DOCS = ROOT / 'docs'
KP_ISSUE = DOCS / 'swifttec_kp_issued.json'

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def collect():
    if not (UPSTREAM / 'index.html').is_file():
        raise RuntimeError('SWIFT-TEC upstream checkout is missing')
    slots = verified_slots(KP_ISSUE)
    print('Japan forecast Kp: same-issue SWIFT-TEC NOAA 3-day verified, 24 slots',flush=True)
    handler = lambda *a, **kw: QuietHandler(*a, directory=str(UPSTREAM), **kw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            executable = os.environ.get('SWIFTION_CHROMIUM_EXECUTABLE')
            browser = pw.chromium.launch(headless=True,
                args=['--disable-dev-shm-usage', '--no-sandbox'],
                **({'executable_path': executable} if executable else {}))
            try:
                page = browser.new_page(viewport={'width': 1350, 'height': 850})
                page.on('console', lambda m: print('Japan browser:',m.text[:240],flush=True) if m.type=='error' else None)
                page.on('pageerror', lambda e: print('Japan page error:',str(e)[:240],flush=True))
                page.goto(f'http://127.0.0.1:{server.server_port}/index.html',
                          wait_until='domcontentloaded', timeout=90000)
                page.wait_for_function('''() =>
                  typeof window.swiftIseeRunMeanForecast === 'function' &&
                  typeof window.swiftInstallIsee10DayBaseForecast === 'function'
                ''', timeout=45000)
                # The compact selector is created by SWIFT-TEC in a delayed
                # dashboard bootstrap (550ms). Previously the code checked it
                # immediately and always failed with "ISEE selector missing".
                page.wait_for_selector('#swiftV52TecSource', state='attached', timeout=30000)
                page.evaluate('''(slots) => {
                  const source = document.getElementById('swiftV52TecSource');
                  if (!source || ![...source.options].some(x => x.value==='isee_japan_highres'))
                    throw Error('SWIFT-TEC ISEE Japan forecast option unavailable');
                  if (typeof gKpSeries === 'undefined')
                    throw Error('SWIFT-TEC internal Kp time series is unavailable');
                  source.value = 'isee_japan_highres';
                  window.swiftV52SyncForecastControls?.();
                  const now = new Date();
                  now.setUTCSeconds(0,0);
                  now.setUTCMinutes(Math.floor(now.getUTCMinutes()/30)*30);
                  const valid = slots.map(x => ({start:Date.parse(x.valid_from_utc),kp:Number(x.kp)}));
                  const last = valid[valid.length-1];
                  const series = [];
                  for (let k=0;k<=192;k++) {
                    const t = new Date(now.getTime() + k*1800000);
                    const ms=t.getTime();
                    const kpSlot=valid.find(s => s.start<=ms && ms<s.start+10800000)
                      || (ms >= last.start+10800000 ? last : valid[0]);
                    series.push({t,kp:kpSlot.kp});
                  }
                  // The model's original makeForecastKpSeries will reuse
                  // gKpSeries (and its original nearest-time policy).
                  gKpSeries = series;
                  // Explicitly avoid an unrelated textarea/manual forecast.
                  const txt=document.getElementById('noaaKpText');
                  if(txt)txt.value='';
                  const autoplay=document.getElementById('movieAutoPlayAfterLoad');
                  if(autoplay)autoplay.checked=false;
                  const install=window.swiftInstallIsee10DayBaseForecast;
                  window.swiftInstallIsee10DayBaseForecast=(frames,kp,meta)=>{
                    window.__swiftIonJapanForecast={frames,kp,meta};
                    return install(frames,kp,meta);
                  };
                  window.__swiftIonJapanKpPrepared={count:series.length,first:series[0].t.toISOString(),
                    heldAfter3Days:true,source:'SWIFTTEC_SAME_ISSUE_NOAA_3DAY'};
                }''', slots)
                # Call the original ISEE forecast directly. The dashboard's
                # wrapper catches errors and returns success with no frames.
                # Calling the model directly exposes real data-source errors.
                page.set_default_timeout(240000)
                page.evaluate('''async () => {
                  await window.swiftIseeRunMeanForecast();
                  if (!window.__swiftIonJapanForecast?.frames?.length)
                    throw Error('Original SWIFT-TEC ISEE forecast yielded no frames');
                }''')
                data = page.evaluate('''() => {
                  const source=window.__swiftIonJapanForecast,frames=source.frames;
                  if(frames.length<48)throw Error('ISEE forecast has fewer than 48 frames: '+frames.length);
                  const meta=frames[0].gridMeta||source.meta?.gridMeta;
                  const allLat=meta?.latArr||[],allLon=meta?.lonArr||[];
                  if(allLat.length<10||allLon.length<10)throw Error('Invalid ISEE grid axes');
                  const lat=allLat.map((v,i)=>({v:Number(v),i})).sort((a,b)=>a.v-b.v);
                  const lon=allLon.map((v,i)=>({v:Number(v),i})).sort((a,b)=>a.v-b.v);
                  const times=[],values=[];
                  for(const f of frames){
                    const dt=new Date(f.time||f.time_utc);
                    if(!Number.isFinite(dt.getTime()))throw Error('Bad forecast timestamp');
                    if(dt.getUTCMinutes()%30!==0||dt.getUTCSeconds()!==0)continue;
                    const row=[];
                    for(const a of lat)for(const b of lon){
                      const v=f.grid?.[a.i]?.[b.i];
                      row.push(typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1000?
                        Math.round(v*10):null);
                    }
                    times.push(dt.toISOString());values.push(row);
                  }
                  const prepared=window.__swiftIonJapanKpPrepared;
                  if(!prepared||prepared.count!==193)throw Error('Kp series not seeded');
                  return {latitudes:lat.map(x=>x.v),longitudes:lon.map(x=>x.v),
                    time_utc:times,values};
                }''')
            finally:
                browser.close()
        return data
    finally:
        server.shutdown()


def main():
    data = collect()
    lat,lon,times = data['latitudes'],data['longitudes'],data['time_utc']
    if not (20<=min(lat)<max(lat)<=50 and 115<=min(lon)<max(lon)<=160):
        raise RuntimeError('Japanese forecast grid outside expected ISEE bounds')
    if len(times)<48:
        raise RuntimeError('Insufficient 30-minute ISEE forecast times')
    out = DOCS / 'japan_animation'
    issued = datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    idx = create_animation(out,times,lat,lon,data['values'],generated_at=issued,
        source_stage=('SWIFT-TEC ISEE Japan time-of-day mean + same-issue NOAA 3-day Kp '
                      '+ Japan grid AI; Kp beyond original NOAA 3 days held at last value; research forecast'),
        chunk_size=8)
    idx['metadata'].update({
        'source_region':'japan',
        'is_isee_observation':False,
        'is_swifttec_isee_forecast':True,
        'source_method':'Captured original SWIFT-TEC ISEE calculated frames; NOT global crop',
        'kp_source_mode':'SWIFTTEC_SAME_ISSUE_NOAA_3DAY',
        'kp_after_three_days':'LAST_VERIFIED_KP_HELD_FOR_EXPERIMENTAL_EXTENSION',
        'forecast_time_utc_start':times[0],
        'forecast_time_utc_end':times[-1],
    })
    (out/'index.json').write_text(json.dumps(idx,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8')
    print('SWIFT-TEC ISEE Japan forecast exported:',check_animation(out,expected_min_frames=48),flush=True)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('SWIFT-TEC Japan ISEE forecast FAILED (no global substitute):',str(exc),file=sys.stderr)
        sys.exit(1)
