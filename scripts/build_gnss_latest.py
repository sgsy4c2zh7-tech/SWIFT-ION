"""Export ONE latest-only GNSS TLE snapshot from the existing SWIFT-TEC checkout.

No GNSS archive is created or modified. The output file at docs/gnss_latest.json
is atomically replaced on every SWIFT-ION Pages build; the SGP4 library is
mirrored from SWIFT-TEC's already-vendored satellite.js.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

GROUPS = ('gps', 'qzss', 'galileo', 'glonass', 'beidou')
SCHEMA = 'swift-ion-latest-gnss-v1'

def read_tle(text, system, gps_health=None):
    records=[]
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    k=0; seen=set()
    while k+2<len(lines):
        name,line1,line2=lines[k:k+3]
        k+=3
        if not(line1.startswith('1 ') and line2.startswith('2 ') and len(line1)>=32 and len(line2)>=63):
            continue
        norad=line1[2:7].strip()
        if norad!=line2[2:7].strip() or not norad.isdecimal() or norad in seen:
            continue
        seen.add(norad)
        match=re.search(r'PRN\s*(\d{1,2})',name,re.IGNORECASE)
        prn=match.group(1).zfill(2) if match else None
        health=gps_health.get(prn) if gps_health and system=='gps' and prn else None
        records.append(dict(system=system,name=name[:64],norad=norad,prn=prn,health=health,line1=line1,line2=line2))
    return records

def build(upstream, output, vendor):
    source=Path(upstream)/'docs'/'data'/'gnss';output=Path(output);vendor=Path(vendor)
    sats=[];source_summary={};gps_health={};source_updated=None
    try:
        health_file=source/'gps_almanac_health.json'
        if health_file.exists():
            gps_health=json.loads(health_file.read_text(encoding='utf-8')).get('health_by_prn',{})
    except (ValueError,OSError):
        pass
    try:
        index=json.loads((source/'index.json').read_text(encoding='utf-8'))
        source_updated=index.get('updated_utc')
    except (ValueError,OSError):
        index={}
    for group in GROUPS:
        path=source/f'{group}_latest.tle'
        try:records=read_tle(path.read_text(encoding='utf-8'),group,gps_health)
        except OSError: records=[]
        source_summary[group]=len(records)
        sats.extend(records)
    info={
        'schema':SCHEMA,
        'generated_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'source_updated_utc':source_updated,
        'source':'SWIFT-TEC docs/data/gnss/*_latest.tle (one latest snapshot only)',
        'health_source':'SWIFT-TEC YUMA GPS almanac if present; other constellation health unverified',
        'status':'AVAILABLE' if sats else 'UNAVAILABLE',
        'satellite_counts':source_summary,
        'is_latest_only':True,'historical_tle_retained':False,
        'limits':{'tle_age_rejection_enabled':False,'positioning_error_is_observed':False,
                  'model':'single-frequency L1 uncorrected first-order ionosphere; SGP4; equal-weight position/clock LS',
                  'warning':'Research-only L1-equivalent display; TLE propagation is not age-limited but accuracy degrades away from epoch; constellation-specific carrier group delays, receiver corrections, and performance are not validated.'},
        'satellites':sats,
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    tmp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=output.parent,delete=False) as f:
            tmp=Path(f.name)
            json.dump(info,f,ensure_ascii=False,separators=(',',':'))
        os.replace(tmp,output)
    finally:
        if tmp is not None and tmp.exists(): tmp.unlink()
    src=Path(upstream)/'docs'/'vendor'/'satellite.min.js'
    if src.exists():
        vendor.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,vendor)
    print(f'GNSS current-only snapshot: {len(sats)} satellites | {output.stat().st_size} bytes | SGP4 vendor: {vendor.exists()}')
    return info

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--upstream',default='_upstream_swifttec')
    parser.add_argument('--output',default='docs/gnss_latest.json')
    parser.add_argument('--vendor',default='docs/vendor/satellite.min.js')
    args=parser.parse_args()
    build(args.upstream,args.output,args.vendor)
