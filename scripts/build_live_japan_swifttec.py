"""Bridge the ACTUAL ISEE-based SWIFT-TEC Japan VTEC forecast into SWIFT-ION.

Calls SWIFT-TEC's own `swiftV52RunForecast` with isee_japan_highres selected,
intercepts `swiftInstallIsee10DayBaseForecast` without altering its computation,
exports its 30-minute Japan VTEC forecast on the native Japan grid, overwriting
only docs/japan_animation/. No observational ISEE archives or forecast history
are published/copied to SWIFT-ION.
"""
from __future__ import annotations
import json,math,sys,threading
from datetime import datetime,timezone
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright
from animation_format import create_animation,check_animation

ROOT=Path(__file__).resolve().parents[1]
UPSTREAM=ROOT/'_upstream_swifttec'/'docs'
DOCS=ROOT/'docs'
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def collect():
    if not (UPSTREAM/'index.html').exists():
        raise RuntimeError('SWIFT-TEC upstream checkout is missing')
    handler=lambda *args,**kw: QuietHandler(*args,directory=str(UPSTREAM),**kw)
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--disable-dev-shm-usage'])
            try:
                page=browser.new_page(viewport={'width':1350,'height':850})
                page.goto(f'http://127.0.0.1:{server.server_port}/index.html',wait_until='domcontentloaded',timeout=90000)
                page.wait_for_function('typeof window.swiftV52RunForecast === "function" && typeof window.swiftInstallIsee10DayBaseForecast === "function"',timeout=45000)
                page.evaluate('''() => {
                  const install=window.swiftInstallIsee10DayBaseForecast;
                  window.swiftInstallIsee10DayBaseForecast=(frames,kp,meta)=>{
                    window.__swiftIonJapanForecast={frames,meta};
                    return install(frames,kp,meta);
                  };
                  const selector=document.getElementById('swiftV52TecSource');
                  if(!selector)throw Error('SWIFT-TEC ISEE selector missing');
                  selector.value='isee_japan_highres';
                  selector.dispatchEvent(new Event('change',{bubbles:true}));
                  window.swiftV52SyncForecastControls?.();
                  const autoplay=document.getElementById('movieAutoPlayAfterLoad');
                  if(autoplay)autoplay.checked=false;
                }''')
                page.set_default_timeout(240000)
                page.evaluate('''async () => {
                  await window.swiftV52RunForecast();
                  if(!window.__swiftIonJapanForecast?.frames?.length)
                    throw Error('SWIFT-TEC ISEE model did not produce forecast frames');
                }''')
                data=page.evaluate('''() => {
                  const source=window.__swiftIonJapanForecast;
                  const frames=source.frames;
                  if(frames.length<48)throw Error('Insufficient ISEE forecast frames: '+frames.length);
                  const meta=frames[0].gridMeta||source.meta?.gridMeta;
                  const allLat=meta?.latArr||[],allLon=meta?.lonArr||[];
                  if(allLat.length<10||allLon.length<10)throw Error('Invalid ISEE forecast grid coordinates');
                  const lat=allLat.map((v,i)=>({v:Number(v),i})).sort((a,b)=>a.v-b.v);
                  const lon=allLon.map((v,i)=>({v:Number(v),i})).sort((a,b)=>a.v-b.v);
                  const times=[];const values=[];
                  for(const f of frames){
                    const dt=new Date(f.time||f.time_utc);
                    if(!Number.isFinite(dt.getTime()))throw Error('Bad forecast time');
                    if(dt.getUTCMinutes()%30!==0||dt.getUTCSeconds()!==0)continue;
                    const grid=f.grid;
                    const row=[];
                    for(const a of lat)for(const b of lon){
                      const v=grid?.[a.i]?.[b.i];
                      row.push(typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1000?Math.round(v*10):null);
                    }
                    times.push(dt.toISOString());values.push(row);
                  }
                  return {latitudes:lat.map(x=>x.v),longitudes:lon.map(x=>x.v),time_utc:times,values};
                }''')
            finally:browser.close()
        return data
    finally:
        server.shutdown()

def main():
    data=collect()
    lat,lon,times=data['latitudes'],data['longitudes'],data['time_utc']
    if not(20<=min(lat)<max(lat)<=50 and 115<=min(lon)<max(lon)<=160):
        raise RuntimeError('SWIFT-TEC Japan forecast grid is outside known ISEE bounds')
    if len(times)<48:raise RuntimeError('Too few 30-minute ISEE forecast timestamps')
    out=DOCS/'japan_animation'
    issued=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    idx=create_animation(out,times,lat,lon,data['values'],generated_at=issued,
        source_stage='SWIFT-TEC ISEE Japan time-of-day mean + forecast Kp + Japan grid-cell AI; research forecast',chunk_size=8)
    idx['metadata']['source_region']='japan'
    idx['metadata']['is_isee_observation']=False
    idx['metadata']['is_swifttec_isee_forecast']=True
    idx['metadata']['source_method']='captured original SWIFT-TEC ISEE computed forecast frames; NOT global crop'
    idx['metadata']['forecast_time_utc_start']=times[0]
    idx['metadata']['forecast_time_utc_end']=times[-1]
    (out/'index.json').write_text(json.dumps(idx,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8')
    print('SWIFT-TEC ISEE Japan forecast exported:',check_animation(out,expected_min_frames=48),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as ex:
        print('SWIFT-TEC Japan ISEE forecast unavailable (NO global substitution):',str(ex),file=sys.stderr)
        sys.exit(1)
