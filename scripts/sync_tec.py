"""Automatic read-only import of an explicitly published SWIFT-TEC CSV URL.
Fail closed rather than present NOAA observations as SWIFT-TEC forecasts.
"""
import os,sys,urllib.request,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from import_swift_tec_csv import import_csv

def main():
    url=os.environ.get('SWIFT_TEC_CSV_URL','').strip()
    if not url:
        print('SWIFT_TEC_CSV_URL not configured: no automatic SWIFT-TEC forecast export exists at a verified public URL.');return 0
    if not url.startswith('https://'):
        raise ValueError('Only HTTPS URLs are allowed')
    req=urllib.request.Request(url,headers={'User-Agent':'SWIFT-ION-public-readonly/0.4'})
    with urllib.request.urlopen(req,timeout=40) as response:
        data=response.read(80_000_001)
    if len(data)>80_000_000:raise ValueError('CSV exceeds 80 MB limit')
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'forecast.csv';p.write_bytes(data);result=import_csv(p)
    result['metadata']['sync_url']=url
    output=ROOT/'docs/swift_tec_vtec.json'
    output.write_text(json.dumps(result,separators=(',',':')),encoding='utf-8')
    print('Updated',output,len(result['frames']),'frames')
    return 0
if __name__=='__main__':sys.exit(main())
