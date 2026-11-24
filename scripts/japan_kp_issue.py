"""Validate the original, same-issue NOAA 3-day Kp used in SWIFT-TEC.

Read-only. The 24 genuine forecast slots are the input to SWIFT-TEC Japan's
existing model; never replace missing slots with observed Kp or Kp=3.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

UTC = timezone.utc
SCHEMA = 'swift-ion-swifttec-issue-kp3day-v1'
MODE = 'SWIFTTEC_SAME_ISSUE_NOAA_3DAY'


def parse_utc(v):
    out = datetime.fromisoformat(str(v).replace('Z', '+00:00'))
    if out.tzinfo is None:
        raise ValueError('Kp timestamp must include timezone')
    return out.astimezone(UTC)


def verified_slots(path, now=None):
    """Return 24 forecast slots, or fail without silently substituting Kp."""
    now = now or datetime.now(UTC)
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    if doc.get('schema') != SCHEMA or doc.get('source_mode') != MODE:
        raise ValueError('Same-issue SWIFT-TEC NOAA Kp provenance is not verified')
    generated = parse_utc(doc['generated_at'])
    if not (-timedelta(minutes=5) <= now - generated <= timedelta(hours=3)):
        raise ValueError('SWIFT-TEC Kp issue file is stale or from the future')
    begin = parse_utc(doc['valid_from_utc'])
    end = parse_utc(doc['valid_until_exclusive_utc'])
    if end - begin != timedelta(days=3):
        raise ValueError('Expected an exact three-day Kp issue period')
    slots = doc.get('slots') or []
    if len(slots) != 24:
        raise ValueError('Expected exactly 24 NOAA Kp 3-hour slots')
    result = []
    for i, r in enumerate(slots):
        t = parse_utc(r['valid_from_utc'])
        if t != begin + i * timedelta(hours=3):
            raise ValueError(f'Kp time slot {i} is missing, duplicated or unordered')
        val = r.get('kp')
        if isinstance(val, bool):
            raise ValueError('Invalid boolean Kp')
        try:
            kp = float(val)
        except (TypeError, ValueError) as exc:
            raise ValueError(f'Invalid NOAA Kp at slot {i}') from exc
        if not 0 <= kp <= 9:
            raise ValueError(f'Out-of-range NOAA Kp at slot {i}')
        result.append({'valid_from_utc': t.isoformat().replace('+00:00','Z'), 'kp': kp})
    return result
