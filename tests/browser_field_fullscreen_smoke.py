"""Offline Chromium test of foF2 map-only fullscreen and control restoration."""
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
STUB = '''
const PALETTES={turbo:[[12,33,130],[40,150,220]]};
function valid(v){return typeof v==='number'&&Number.isFinite(v)}
function clamp(v,a,b){return Math.max(a,Math.min(b,v))}
function distanceKm(a,b,c,d){return Math.hypot(a-c,b-d)*100}
function latitudeAtMercatorFraction(n,s,f){return n*(1-f)+s*f}
function coverageAlpha(){return 1}
const COVERAGE_LIMIT_KM={japan:750,global:3000};
const CONTOUR_OPTIONS={fof2:{steps:[.5,1,2],preferred:1,unit:'MHz'},hmf2:{steps:[25,50],preferred:50,unit:'km'},tec:{steps:[5,10],preferred:10,unit:'TECU'},ne:{steps:[.1,.2],preferred:.2,unit:'log'}};
function drawFieldOverlays(){}
const tiles={addTo(){return this},getContainer(){return {style:{}}},on(){return this}};
window.L={
 map(){return {layers:new Set(),createPane(){},getPane(){return {style:{}}},on(){return this},
  fitBounds(){return this},invalidateSize(){return this},removeLayer(obj){this.layers.delete(obj)},
  hasLayer(obj){return this.layers.has(obj)}}},
 tileLayer(){return {...tiles}},latLngBounds(x){return x},
 layerGroup(){return {addTo(){return this},clearLayers(){}}},
 imageOverlay(){return {addTo(map){map.layers.add(this);return this},setBounds(){},setUrl(){},setOpacity(){}}},
 circleMarker(){return {addTo(){}}}, popup(){return {setLatLng(){return this},setContent(){return this},openOn(){return this}}}
};
window.fetch=async()=>({ok:true,json:async()=>({schema:'swift-ion-iri-tec-forecast-v1',status:'TEST',
 metadata:{issued_at:'2026-11-23T00:00:00Z'},altitudes_km:[300],frames:[
 {valid_at:'2026-11-23T00:00:00Z',sites:[{lat:35,lon:139,fof2_iri_mhz:6.2,fof2_tec_mhz:6.4,hmf2_iri_km:310}]},
 {valid_at:'2026-11-23T00:30:00Z',sites:[{lat:35,lon:139,fof2_iri_mhz:7.1,fof2_tec_mhz:7.3,hmf2_iri_km:320}]}
]})});
'''

def run():
 html=(ROOT/'docs/field.html').read_text(encoding='utf-8')
 html=html.replace('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">','')
 html=html.replace('<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>','')
 for line in html.splitlines():
  if line.startswith('import '):html=html.replace(line,'')
 html=html.replace('<script type="module">','<script>(async()=>{'+STUB)
 html=html.replace('</script></body></html>','})();</script></body></html>')
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').is_file() else None,args=['--no-sandbox'])
  try:
   page=browser.new_page(viewport={'width':1280,'height':800})
   errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
   page.set_content(html,wait_until='domcontentloaded')
   page.wait_for_function("document.getElementById('seek').disabled === false")
   assert page.locator('#fieldMapHud').is_hidden()
   page.locator('#fullscreen').click()
   page.wait_for_function("document.fullscreenElement?.id === 'area'")
   assert page.locator('#fieldMapHud').is_visible()
   assert page.evaluate("document.getElementById('fieldControls').parentElement.id")=='fieldMapHud'
   assert page.evaluate("document.getElementById('seek').parentElement.id")=='fieldMapHud'
   assert page.evaluate("document.getElementById('timeLabel').getBoundingClientRect().right")>1200
   page.locator('#next').click()
   page.wait_for_function("document.getElementById('timeLabel').textContent.includes('00:30')")
   page.locator('#fullscreen').click()
   page.wait_for_function('document.fullscreenElement === null')
   assert page.evaluate("document.getElementById('fieldControls').parentElement.tagName")=='BODY'
   assert page.evaluate("document.getElementById('seek').parentElement.id")=='workspace'
   assert page.evaluate("document.getElementById('fieldLegend').parentElement.id")=='workspace'
   assert not errors, errors
   print('foF2 map-only fullscreen, top-right time, 30-min playback, exit/restore PASS')
  finally:browser.close()
if __name__=='__main__':run()
