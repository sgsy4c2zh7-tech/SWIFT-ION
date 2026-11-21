"""Read SWIFT-TEC's 4-day CSV export without modifying the source repository.
Only generates a VTEC map; does NOT infer ionospheric layer density from TEC.
"""
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'data/input/swifttec_forecast.csv'
OUTPUT = ROOT / 'docs/swift_tec_vtec.json'
REQUIRED = {'time_utc', 'lat', 'lon', 'tec_tecu', 'gpsL1_m'}

def parse_utc(raw):
    dt = datetime.fromisoformat(raw.strip().replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp must include UTC offset')
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00','Z')

def import_csv(path):
    grouped = defaultdict(list)
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not REQUIRED.issubset(set(reader.fieldnames or [])):
            raise ValueError(f'CSV missing columns: {sorted(REQUIRED - set(reader.fieldnames or []))}')
        for row in reader:
            t = parse_utc(row['time_utc'])
            lat, lon, tec = float(row['lat']), float(row['lon']), float(row['tec_tecu'])
            if not all(map(math.isfinite, [lat, lon, tec])) or not (-90 <= lat <= 90 and -180 <= lon <= 180 and 0 <= tec <= 1000):
                raise ValueError('Invalid coordinate or VTEC value')
            grouped[t].append({'lat':lat,'lon':lon,'vtec_tecu':tec})
    if not grouped:
        raise ValueError('No CSV rows')
    times = sorted(grouped)
    return {'metadata':{'source':'SWIFT-TEC browser CSV export','source_stage':'unverified',
                        'kind':'VTEC_FORECAST_IMPORT','is_forecast':True,
                        'warning':'Imported VTEC only; not validated ionospheric layer predictions.',
                        'units':'TECU','times_utc':times},
            'frames':[{'valid_at':t,'cells':grouped[t]} for t in times]}

if __name__ == '__main__':
    path = Path(sys.argv[1]) if len(sys.argv)>1 else INPUT
    if not path.exists():
        print('No SWIFT-TEC CSV found; existing synthetic demo is preserved.')
        sys.exit(0)
    data=import_csv(path)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
    print(f"Imported {len(data['frames'])} time frames to {OUTPUT}")
