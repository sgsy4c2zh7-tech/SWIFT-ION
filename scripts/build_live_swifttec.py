"""Run upstream SWIFT-TEC read-only and export native TEC plus the EXACT NOAA
3-day Kp slots used in that same browser run. Kp beyond the parsed three days
is deliberately excluded from issue-provenance even though upstream may hold
its final slot into its 5-day animation. No synthetic Kp is published.
"""
import json, sys, threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
from animation_format import create_animation

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'_upstream_swifttec'/'docs'
DOCS=ROOT/'docs'

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def main():
    if not (SOURCE/'index.html').is_file():raise RuntimeError('SWIFT-TEC upstream checkout missing')
    handler=lambda *args,**kw:QuietHandler(*args,directory=str(SOURCE),**kw)
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--disable-dev-shm-usage'])
            try:
                page=browser.new_page(viewport={'width':1280,'height':900})
                page.on('console',lambda m:print('Browser:',m.text[:250]) if m.type=='error' else None)
                page.goto(f'http://127.0.0.1:{server.server_port}/index.html',wait_until='domcontentloaded',timeout=90000)
                page.wait_for_function("typeof fetchNoaaGloTecPrevDay12_2hour === 'function' && typeof runForecast === 'function'",timeout=30000)
                page.select_option('#tecSourceSelect','noaa')
                page.evaluate('fetchNoaaGloTecPrevDay12_2hour(false)')
                page.wait_for_function("document.getElementById('noaaTecStatus')?.textContent?.includes('loaded into memory') || document.getElementById('noaaTecStatus')?.textContent?.startsWith('Failed:')",timeout=180000)
                status=page.locator('#noaaTecStatus').inner_text()
                if status.startswith('Failed:'):raise RuntimeError('NOAA TEC loading failed: '+status)
                page.evaluate('fetchNoaa3DayGeomagToTextarea()')
                page.wait_for_function("document.getElementById('noaa3dayStatus')?.textContent?.trim() === 'OK' || document.getElementById('noaa3dayStatus')?.textContent?.startsWith('Failed:')",timeout=45000)
                if page.locator('#noaa3dayStatus').inner_text().strip()!='OK':raise RuntimeError('NOAA Kp forecast unavailable')
                page.evaluate('fetchNoaaPlanetaryKIndex1DayToBase()')
                page.wait_for_function("(document.getElementById('baseKpJson')?.value || '').length > 20",timeout=45000)
                page.evaluate('runForecast()')
                page.wait_for_function('typeof gForecastFrames !== "undefined" && gForecastFrames.length > 0',timeout=180000)
                data=page.evaluate(r'''() => {
                  if (!gGrid || !gForecastFrames.length || gForecastFrames.length !== gForecastTimes.length)
                    throw Error('Incomplete forecast');
                  const lat=gGrid.latArr.map((x,i)=>({v:Number(x),i})).sort((a,b)=>a.v-b.v);
                  const ll=gGrid.lonArr.map((x,i)=>({v:((Number(x)+180)%360+360)%360-180,i})).sort((a,b)=>a.v-b.v);
                  const lon=[];for(const e of ll){if(!lon.length||Math.abs(e.v-lon[lon.length-1].v)>1e-6)lon.push(e)}
                  if(lat.length<20||lon.length<20)throw Error('Grid unexpectedly sparse');
                  const times=gForecastTimes.map(x=>x.toISOString());
                  const frames=[];
                  for(const frame of gForecastFrames){
                    const row=[];
                    for(const a of lat){for(const b of lon){
                      const v=frame[a.i]?.[b.i];
                      row.push(Number.isFinite(v)&&v>=0&&v<=1000?Math.round(v*10):null);
                    }}frames.push(row);
                  }
                  // The upstream browser uses a 5-day series. A NOAA 3-day Kp
                  // forecast is only justified over the actual parsed daily slots.
                  let kpIssue={status:'UNVERIFIED',reason:'NOAA forecast Kp provenance unavailable'};
                  try{
                    const sourceDays=parseNoaa3DayGeomag(document.getElementById('noaaKpText').value||'');
                    if(sourceDays.length!==3||!Array.isArray(gKpSeries)||gKpSeries.length!==times.length)
                      throw Error('Missing exact 3-day NOAA Kp provenance');
                    const slots=sourceDays.flatMap(d=>d.slots.map(s=>({
                      valid_from_utc:new Date(d.day.getTime()+s.startHour*3600000).toISOString(),
                      kp:Number(s.kp)
                    })));
                    if(slots.length!==24||slots.some(s=>!Number.isFinite(s.kp)||s.kp<0||s.kp>9))
                      throw Error('NOAA 3-day Kp slots are incomplete');
                    const from=sourceDays[0].day.toISOString(),
                          to=new Date(sourceDays[2].day.getTime()+86400000).toISOString();
                    for(let i=0;i<times.length;i++){
                      const ms=gForecastTimes[i].getTime();
                      if(ms<Date.parse(from)||ms>=Date.parse(to))continue;
                      const src=gKpSeries[i]?.kp;
                      const slot=slots.find(s=>Date.parse(s.valid_from_utc)<=ms && ms<Date.parse(s.valid_from_utc)+10800000);
                      if(!slot||!Number.isFinite(src)||Math.abs(slot.kp-src)>1e-5)
                        throw Error('SWIFT-TEC Kp series differs from audited NOAA slots');
                    }
                    kpIssue={status:'VERIFIED',from,to,slots};
                  }catch(e){kpIssue={status:'UNVERIFIED',reason:String(e.message||e).slice(0,180)}}
                  return {latitudes:lat.map(x=>x.v),longitudes:lon.map(x=>x.v),
                    time_utc:times,values:frames,kp_issued:kpIssue,
                    native_grid:{nLat:gGrid.nLat,nLon:gGrid.nLon}};
                }''')
            finally:browser.close()
        generated=datetime.now(timezone.utc).isoformat()
        aligned=(data['kp_issued'].get('status')=='VERIFIED')
        stage=('upstream runForecast; parsed NOAA 3-day Kp independently verified' if aligned else 'upstream runForecast; 3-day Kp provenance UNVERIFIED')
        idx=create_animation(DOCS/'animation',data['time_utc'],data['latitudes'],data['longitudes'],data['values'],generated_at=generated,source_stage=stage)
        # Snapshot only the original, auditable 3-day forecast bins. NEVER
        # represent an up-to-5-day held-final-Kp series as a 3-day forecast.
        kp={'schema':'swift-ion-swifttec-issue-kp3day-v1','generated_at':generated,
            'source':'NOAA 3-day forecast text parsed by upstream SWIFT-TEC in SAME run',
            'source_mode':'SWIFTTEC_SAME_ISSUE_NOAA_3DAY' if aligned else 'UNVERIFIED_NOAA_KP_PROVENANCE',
            'valid_from_utc':data['kp_issued'].get('from'),
            'valid_until_exclusive_utc':data['kp_issued'].get('to'),
            'slots':data['kp_issued'].get('slots',[]),
            'reason':data['kp_issued'].get('reason'),
            'out_of_range_policy':'NO Kp confirmation beyond original 3-day slots, even if upstream TEC continues'}
        (DOCS/'swifttec_kp_issued.json').write_text(json.dumps(kp,separators=(',',':'),allow_nan=False),encoding='utf-8')
        ny=len(data['latitudes']);nx=len(data['longitudes'])
        lat_indices=range(0,ny,5);lon_indices=range(0,nx,2)
        frames=[]
        for s in range(0,len(data['time_utc']),4):
            values=data['values'][s];cells=[]
            for i in lat_indices:
                for j in lon_indices:
                    v=values[i*nx+j]
                    if v is not None:
                        cells.append({'lat':data['latitudes'][i],'lon':data['longitudes'][j],'vtec_tecu':round(v/10,2)})
            if len(cells)<500:raise RuntimeError(f'Legacy sampled frame has too few cells: {len(cells)}')
            frames.append({'valid_at':data['time_utc'][s],'cells':cells})
        result={'frames':frames,'grid':{'original_lat':data['native_grid']['nLat'],
                'original_lon':data['native_grid']['nLon'],
                'sampled_lat':len(lat_indices),'sampled_lon':len(lon_indices)},
                'upstream_model':'SWIFT-TEC browser runForecast','time_step_minutes':120,
                'metadata':{'source':'SWIFT-TEC browser calculation (read-only upstream)',
                    'kind':'VTEC_FORECAST','is_forecast':True,'source_stage':stage,
                    'generated_at':generated,'units':'TECU','sampled_for_web':True,
                    'kp3day_issue_provenance':'swifttec_kp_issued.json',
                    'warning':'Experimental, unvalidated VTEC forecast. Does not determine navigation availability or ionospheric layer forecasts.',
                    'animation_url':'./animation/index.json'}}
        (DOCS/'swift_tec_vtec.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False),encoding='utf-8')
        print('SWIFT-TEC legacy frames:',len(frames),'sample cells:',len(frames[0]['cells']),
              'native animation',len(idx['time_utc']),'frames; NOAA Kp issue',kp['source_mode'],len(kp['slots']),'slots',flush=True)
    finally:server.shutdown()
if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('SWIFT-TEC automation FAILED:',str(exc),file=sys.stderr);sys.exit(1)
