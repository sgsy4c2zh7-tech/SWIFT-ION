"""Optional Chromium UI smoke test; stubs are injected into memory, never deployed.
This checks fullscreen DOM transitions independently of external data/CDNs.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
STUB = '''
window.L={map:function(id){const el=document.getElementById(id);return {setView(){return this},getSize(){return {x:el.clientWidth,y:el.clientHeight}},containerPointToLatLng(p){return {lat:50-100*p[1]/Math.max(1,el.clientHeight),lng:-180+360*p[0]/Math.max(1,el.clientWidth)}},latLngToContainerPoint(p){const lat=p[0],lon=p[1];return{x:(lon+180)/360*el.clientWidth,y:(50-lat)/100*el.clientHeight}},invalidateSize(){return this},on(){return this}}},tileLayer(){return{addTo(){return this}}}};
window.satellite={};
class ForecastCube {constructor(){this.nx=4;this.ny=4;this.latitudes=[-60,-20,20,60];this.longitudes=[-180,-90,0,90];this.scale=10;this.index={metadata:{source_stage:'test',generated_at:'2026-11-23'}}}async load(){this.times=[Date.parse('2026-11-23T00:00:00Z'),Date.parse('2026-11-23T00:30:00Z')]}async frame(i){return Array.from({length:16},(_,n)=>100+i*10+n)}}
function renderRaster(c){const p=c.parentElement;c.width=p.clientWidth;c.height=p.clientHeight;const x=c.getContext('2d');x.fillStyle='#225d86';x.fillRect(0,0,c.width,c.height)}
function spatial(c,v){return v?5:null}function interpolateColor(){return [20,120,140,200]}
function prepareSatellites(){throw Error('test fixture intentionally has no GNSS')};function propagateSnapshot(){return []}function buildGnssGrid(){return null};const MAX_TLE_AGE_HOURS=72;
function drawContours(){return null}
'''

def run():
  html=(ROOT/'docs/animate.html').read_text()
  html=html.replace('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">','')
  html=html.replace('<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>','')
  html=html.replace('<script src="./vendor/satellite.min.js"></script>','')
  import_lines=[line for line in html.splitlines() if line.startswith('import ')]
  for line in import_lines:html=html.replace(line,'')
  html=html.replace('<script type="module">', '<script>(async()=>{'+STUB)
  html=html.replace('</script></body></html>', '})();</script></body></html>')
  with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').is_file() else None,args=['--no-sandbox'])
    try:
      page=browser.new_page(viewport={'width':1280,'height':800})
      page.set_content(html,wait_until='domcontentloaded')
      page.wait_for_function('document.getElementById("play").disabled === false',timeout=10000)
      assert page.evaluate('document.getElementById("timeHud").getBoundingClientRect().width')==0
      page.locator('#fullscreen').click()
      page.wait_for_function('document.fullscreenElement?.id === "map"')
      assert page.locator('#timeHud').is_visible()
      assert page.evaluate('document.getElementById("toolbar").parentElement.id')=='mapHud'
      assert page.evaluate('document.getElementById("seek").parentElement.id')=='mapHud'
      assert page.locator('#timeHud').inner_text().strip()
      page.locator('#next').click()
      page.wait_for_function('document.getElementById("counter").textContent.startsWith("2 /")')
      page.locator('#fullscreen').click()
      page.wait_for_function('document.fullscreenElement === null')
      assert page.evaluate('document.getElementById("toolbar").parentElement.id')=='panel'
      assert page.evaluate('document.getElementById("seek").parentElement.id')=='panel'
      page.locator('#mode').select_option('iono_h')
      page.wait_for_function('document.getElementById("status").textContent.includes("GNSS")')
      print('Fullscreen HUD + 30-min playback + exit/restore + GNSS missing-data state PASS')
    finally:browser.close()
if __name__=='__main__':run()
