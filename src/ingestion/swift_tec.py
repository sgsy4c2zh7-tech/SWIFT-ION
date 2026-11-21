"""Validate local SWIFT-TEC export. Read-only; no network writes."""
import json
from datetime import datetime, timezone
from pathlib import Path

def _utc(s):
    if not isinstance(s,str):raise ValueError('timestamp must be string')
    dt=datetime.fromisoformat(s.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('timezone required')
    return dt.astimezone(timezone.utc)

def load_export(path):
    obj=json.loads(Path(path).read_text(encoding='utf-8'))
    if obj.get('schema_version')!='swift-ion-tec-v1':raise ValueError('Unsupported schema')
    issued=_utc(obj['issued_at']);valid=_utc(obj['valid_at'])
    if valid<issued:raise ValueError('valid_at before issued_at')
    if obj.get('source')!='SWIFT-TEC':raise ValueError('Unexpected source')
    cells=obj.get('cells')
    if not isinstance(cells,list) or not cells:raise ValueError('cells required')
    for c in cells:
        lat,lon,tec=float(c['lat']),float(c['lon']),float(c['vtec_tecu'])
        if not(-90<=lat<=90 and -180<=lon<=180 and 0<=tec<1000):raise ValueError('Invalid grid cell')
    return obj
