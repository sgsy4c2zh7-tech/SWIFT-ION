"""Run the upstream SWIFT-TEC browser calculation headlessly; publish sampled VTEC.
No modification to upstream repository. Failure exits nonzero rather than faking data.
"""
import argparse, json, math, os, subprocess, sys, threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '_upstream_swifttec' / 'docs'
OUTPUT = ROOT / 'docs' / 'swift_tec_vtec.json'

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

def main():
    if not (SOURCE / 'index.html').exists():
        raise RuntimeError('Upstream SWIFT-TEC docs/index.html missing; clone upstream first')
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(SOURCE), **kwargs)
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
            page = browser.new_page(viewport={'width':1280,'height':900})
            page.on('console', lambda m: print('Browser:', m.text[:300]) if m.type == 'error' else None)
            page.goto(f'http://127.0.0.1:{server.server_port}/index.html', wait_until='domcontentloaded', timeout=90000)
            page.wait_for_function("typeof fetchNoaaGloTecPrevDay12_2hour === 'function' && typeof runForecast === 'function'", timeout=30000)
            page.select_option('#tecSourceSelect', 'noaa')
            page.evaluate('fetchNoaaGloTecPrevDay12_2hour(false)')
            page.wait_for_function("document.getElementById('noaaTecStatus')?.textContent?.includes('loaded into memory') || document.getElementById('noaaTecStatus')?.textContent?.startsWith('Failed:')", timeout=180000)
            status=page.locator('#noaaTecStatus').inner_text()
            if status.startswith('Failed:'): raise RuntimeError('NOAA TEC input failed: '+status)
            # Explicitly fetch Kp and base Kp; do not silently accept default Kp=3.
            page.evaluate('fetchNoaa3DayGeomagToTextarea()')
            page.wait_for_function("document.getElementById('noaa3dayStatus')?.textContent?.trim() === 'OK' || document.getElementById('noaa3dayStatus')?.textContent?.startsWith('Failed:')", timeout=45000)
            if page.locator('#noaa3dayStatus').inner_text().strip() != 'OK':
                raise RuntimeError('NOAA Kp forecast unavailable')
            page.evaluate('fetchNoaaPlanetaryKIndex1DayToBase()')
            # Base-Kp function may have its own fallback; verify input exists before running.
            page.wait_for_function("(document.getElementById('baseKpJson')?.value || '').length > 20", timeout=45000)
            page.evaluate('runForecast()')
            page.wait_for_function('typeof gForecastFrames !== "undefined" && gForecastFrames.length > 0', timeout=180000)
            result=page.evaluate('''() => {
              if (!gGrid || !gForecastFrames.length || !gForecastTimes.length) throw Error('Forecast not produced');
              const latIndices = gGrid.latArr.map((v,i)=>i).filter(i=>i%5===0);
              const lonIndices = gGrid.lonArr.map((v,i)=>i).filter(i=>i%2===0);
              const frames=[];
              for(let s=0;s<gForecastFrames.length;s+=4){
                const cells=[];
                for(const i of latIndices) for(const j of lonIndices){
                  const v=gForecastFrames[s][i][j];
                  if(Number.isFinite(v) && v>=0) cells.push({lat:gGrid.latArr[i],lon:gGrid.lonArr[j],vtec_tecu:Math.round(v*100)/100});
                }
                if(cells.length<500) throw Error('Too few valid cells: '+cells.length);
                frames.push({valid_at:gForecastTimes[s].toISOString(),cells});
              }
              return {frames, grid:{original_lat:gGrid.nLat,original_lon:gGrid.nLon,sampled_lat:latIndices.length,sampled_lon:lonIndices.length}, upstream_model:'SWIFT-TEC browser runForecast', time_step_minutes:120};
            }''')
            browser.close()
        if not result['frames']: raise RuntimeError('No forecast frames')
        result['metadata']={'source':'SWIFT-TEC browser calculation (read-only upstream)', 'kind':'VTEC_FORECAST', 'is_forecast':True,'source_stage':'upstream runForecast; ML correction stage not independently verified','generated_at':datetime.now(timezone.utc).isoformat(),'units':'TECU','warning':'Experimental, not validated. NOAA inputs and upstream code can change. Not layer density.', 'sampled_for_web':True}
        OUTPUT.parent.mkdir(parents=True,exist_ok=True)
        OUTPUT.write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
        print('Wrote',OUTPUT, len(result['frames']),'frames',len(result['frames'][0]['cells']),'cells/frame')
    finally:
        server.shutdown()

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('AUTOMATION FAILED:',str(exc),file=sys.stderr)
        sys.exit(1)
