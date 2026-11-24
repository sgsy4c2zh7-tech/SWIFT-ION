"""SWIFT-ION v0.9.1: ionosonde observations vs IRI climatology.

Public KC2G GIRO/INGV-derived station feed. For this source ONLY,
naive ISO datetime strings are interpreted as UTC; the upstream database
model stores measurement timestamps without timezone information.
This is a source-specific, documented assumption, not a universal rule.
No fabricated data. Non-commercial research; station-level attribution required.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / 'docs' / 'ionosonde_validation.json'
KC2G_URL = 'https://prop.kc2g.com/api/stations.json'
ALT_RANGE = [100, 2000, 25]
GIRO_RULES = 'https://giro.uml.edu/didbase/RulesOfTheRoad.html'
STATION_ACKNOWLEDGEMENTS = 'https://giro.uml.edu/didbase/acknowledgements.htm'


def utc(value, *, kc2g_naive_utc=False):
    """Return aware UTC datetime; allow naive UTC only for the KC2G feed."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Observation timestamp must be a non-empty ISO8601 string')
    dt = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    if dt.tzinfo is None:
        if not kc2g_naive_utc:
            raise ValueError('Observation timestamp must specify UTC offset')
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def number(value, low, high):
    if value is None or value == '' or isinstance(value, bool):
        return None
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    return val if math.isfinite(val) and low <= val <= high else None


def schema_diagnostic(body):
    """Expose only structure, never raw public station records in build logs."""
    if not isinstance(body, list):
        return {'type': type(body).__name__}
    first = next((r for r in body if isinstance(r, dict)), None)
    if first is None:
        return {'type': 'list', 'record_type': type(body[0]).__name__ if body else 'empty'}
    station = first.get('station')
    timestamp = first.get('time')
    return {
        'type': 'list',
        'record_keys': sorted(first),
        'station_type': type(station).__name__,
        'station_keys': sorted(station) if isinstance(station, dict) else [],
        'time_type': type(timestamp).__name__,
        'time_has_utc_designator': (isinstance(timestamp, str) and
                                    (timestamp.endswith('Z') or '+' in timestamp[10:] or '-' in timestamp[10:])),
    }


def parse_stations(body, now=None, max_age_hours=6, min_confidence=70):
    """Read KC2G MeasurementSchema (station nested; time UTC with/without offset).

    A failed timestamp is counted as bad_timestamp, not bad_shape.
    Future records, stale records and low-confidence records are excluded.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Reference time must contain timezone')
    if not isinstance(body, list):
        raise ValueError('Expected JSON array from /api/stations.json')
    kept = {}
    skipped = {'bad_shape': 0, 'bad_timestamp': 0, 'stale': 0,
               'bad_coords': 0, 'no_characteristics': 0, 'low_confidence': 0}
    for record in body:
        if not isinstance(record, dict) or not isinstance(record.get('station'), dict):
            skipped['bad_shape'] += 1
            continue
        station = record['station']
        name = str(station.get('name') or '').strip()[:120]
        lat = number(station.get('latitude'), -90, 90)
        lon = number(station.get('longitude'), -360, 360)
        if not name or lat is None or lon is None:
            skipped['bad_coords'] += 1
            continue
        lon = ((lon + 180) % 360) - 180
        try:
            valid_at = utc(record['time'], kc2g_naive_utc=True)
        except (ValueError, KeyError, TypeError, OverflowError):
            skipped['bad_timestamp'] += 1
            continue
        age = (now - valid_at).total_seconds() / 3600
        if age < -0.25 or age > max_age_hours:
            skipped['stale'] += 1
            continue
        fof2 = number(record.get('fof2'), 0.5, 25)
        hmf2 = number(record.get('hmf2'), 150, 700)
        if fof2 is None and hmf2 is None:
            skipped['no_characteristics'] += 1
            continue
        cs = number(record.get('cs'), 0, 100)
        if cs is not None and cs < min_confidence:
            skipped['low_confidence'] += 1
            continue
        obs = {'station': name, 'lat': lat, 'lon': lon,
               'observed_at': valid_at.isoformat().replace('+00:00', 'Z'),
               'fof2_mhz': fof2, 'hmf2_km': hmf2, 'confidence': cs,
               'confidence_known': cs is not None, 'age_hours': round(max(age, 0), 3)}
        key = (name, lat, lon)
        old = kept.get(key)
        if old is None or obs['observed_at'] > old['observed_at']:
            kept[key] = obs
    return sorted(kept.values(), key=lambda x: (x['station'], x['lat'])), skipped


def separation_km(a, b):
    la1, lo1 = math.radians(a['lat']), math.radians(a['lon'])
    la2, lo2 = math.radians(b['lat']), math.radians(b['lon'])
    arg = math.sin(la1)*math.sin(la2) + math.cos(la1)*math.cos(la2)*math.cos(lo1-lo2)
    return 6371 * math.acos(max(-1, min(1, arg)))


def global_sample(records, limit):
    """Geographically balanced selection among the source's REAL stations.

    Deterministically favors underrepresented latitude/longitude sectors.
    It never creates missing observation coordinates or values.
    """
    from station_coverage import balanced_global_sample
    return balanced_global_sample(records, limit)


def error_stats(pairs, unit):
    if not pairs:
        return {'status': 'NO_MATCHES', 'sample_count': 0, 'unit': unit,
                'mae': None, 'rmse': None, 'bias': None}
    diffs = [p - o for p, o in pairs]
    return {'status': 'AVAILABLE', 'sample_count': len(diffs), 'unit': unit,
            'mae': round(statistics.mean(abs(d) for d in diffs), 3),
            'rmse': round(math.sqrt(statistics.mean(d*d for d in diffs)), 3),
            'bias': round(statistics.mean(diffs), 3)}


def compare_station(IRI, obs):
    from build_ionosphere import extract_iri_profile, diagnose
    t = utc(obs['observed_at'])  # Now normalized and explicitly UTC
    ds = IRI(t, ALT_RANGE, obs['lat'], obs['lon'])
    alt, ne = extract_iri_profile(ds)
    metrics = diagnose(alt, ne)
    result = dict(obs)
    result['iri_fof2_mhz'] = metrics['fof2_mhz']
    result['iri_hmf2_km'] = metrics['hmf2_km']
    result['fof2_error_mhz'] = (round(metrics['fof2_mhz'] - obs['fof2_mhz'], 3)
                                if obs['fof2_mhz'] is not None else None)
    result['hmf2_error_km'] = (round(metrics['hmf2_km'] - obs['hmf2_km'], 3)
                              if obs['hmf2_km'] is not None else None)
    result['peak_at_boundary'] = metrics['peak_at_boundary']
    result['f2_peak_method'] = metrics['peak_type']
    return result


def fetch_stations(url=KC2G_URL):
    if url != KC2G_URL:
        raise ValueError('Only the documented KC2G public URL is supported')
    req = urllib.request.Request(url, headers={'User-Agent': 'SWIFT-ION-v0.9.1-research/1.0 (noncommercial)'})
    with urllib.request.urlopen(req, timeout=35) as res:
        content = res.read(5_000_001)
    if len(content) > 5_000_000:
        raise ValueError('Station feed exceeds the 5MB safety limit')
    return json.loads(content)


def status_payload(now, status, message, raw_count=0, skipped=None):
    return {'metadata': {'schema': 'swift-ion-ionosonde-v1.1',
            'generated_at': now.isoformat().replace('+00:00', 'Z'),
            'source': 'KC2G real-time station aggregate (GIRO / INGV derived)',
            'source_url': KC2G_URL,
            'original_providers': 'GIRO participating ionosonde operators / INGV as applicable',
            'rules_url': GIRO_RULES,
            'provider_acknowledgements_url': STATION_ACKNOWLEDGEMENTS,
            'license': 'GIRO-derived data: CC BY-NC-SA 4.0; noncommercial use only',
            'comparison': 'IRI climatology at ionosonde location and actual observation time',
            'is_forecast_skill': False, 'is_operational': False,
            'source_time_policy': 'KC2G timezone-naive ISO timestamps are interpreted as UTC; never apply to arbitrary feeds',
            'hmf2_resolution_note': 'IRI model maxima sampled on 25km altitudes (180-600 km).',
            'warning': 'Model-observation comparison, NOT forecast skill. GIRO data may be auto or manually scaled. Station operator credits required.'},
            'status': status, 'message': message, 'input_station_records': raw_count,
            'skipped': skipped or {}, 'sampled_stations': 0, 'evaluated_stations': 0,
            'metrics': {'fof2': error_stats([], 'MHz'), 'hmf2': error_stats([], 'km')},
            'stations': [], 'errors': []}


def evaluate(raw, now=None, max_stations=32, max_age_hours=6, min_confidence=70, iri_function=None):
    now = now or datetime.now(timezone.utc)
    base = status_payload(now, 'NO_USABLE_OBSERVATIONS', 'No fresh and usable station records')
    base['schema_diagnostic'] = schema_diagnostic(raw)
    records, skipped = parse_stations(raw, now, max_age_hours, min_confidence)
    base['input_station_records'] = len(raw)
    base['skipped'] = skipped
    stations = global_sample(records, max_stations)
    base['sampled_stations'] = len(stations)
    from station_coverage import coverage_summary
    base['coverage'] = coverage_summary(records, stations)
    if not stations:
        if skipped.get('bad_shape') == len(raw) and raw:
            base['status'] = 'SOURCE_SCHEMA_ERROR'
            base['message'] = 'All station records failed structural checks; inspect schema_diagnostic'
        elif skipped.get('bad_timestamp') == len(raw) and raw:
            base['status'] = 'SOURCE_TIME_ERROR'
            base['message'] = 'All station timestamps failed parsing; inspect schema_diagnostic'
        return base
    if iri_function is None:
        try:
            from iri2020 import IRI as iri_function
        except Exception as exc:
            base['status'] = 'IRI_UNAVAILABLE'
            base['message'] = 'IRI import failed: ' + str(exc)[:160]
            return base
    matched = []
    for station in stations:
        try:
            matched.append(compare_station(iri_function, station))
        except Exception as exc:
            base['errors'].append({'station': station['station'], 'error': str(exc)[:150]})
    base['stations'] = matched
    base['evaluated_stations'] = len(matched)
    base['coverage']['iri_comparisons_succeeded'] = len(matched)
    if not matched:
        base['status'] = 'IRI_RUN_FAILED'
        base['message'] = 'IRI did not return any valid station comparisons'
        return base
    base['status'] = 'AVAILABLE'
    base['message'] = f'Compared IRI climatology with {len(matched)} recent station measurements'
    base['metrics'] = {
        'fof2': error_stats([(s['iri_fof2_mhz'], s['fof2_mhz']) for s in matched
                             if s['fof2_mhz'] is not None], 'MHz'),
        'hmf2': error_stats([(s['iri_hmf2_km'], s['hmf2_km']) for s in matched
                             if s['hmf2_km'] is not None and not s['peak_at_boundary']], 'km')}
    return base


def write_output(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False,
                              separators=(',', ':')), encoding='utf-8')
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--input', type=Path, help='Optional approved KC2G JSON snapshot for diagnostics')
    parser.add_argument('--max-stations', type=int, default=32)
    parser.add_argument('--max-age-hours', type=float, default=6)
    parser.add_argument('--min-confidence', type=float, default=70)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    try:
        if args.input:
            raw = json.loads(args.input.read_text(encoding='utf-8'))
        else:
            raw = fetch_stations()
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        result = status_payload(now, 'SOURCE_UNAVAILABLE', 'Cannot retrieve or parse station feed: ' + str(exc)[:180])
    else:
        try:
            result = evaluate(raw, now, args.max_stations, args.max_age_hours, args.min_confidence)
        except (ValueError, TypeError) as exc:
            result = status_payload(now, 'SOURCE_SCHEMA_ERROR', 'Station JSON schema issue: '+str(exc)[:180])
    write_output(args.output, result)
    print('Ionosonde comparison:', result['status'], '; observations:',
          result['evaluated_stations'], '; saved:', args.output, flush=True)
    print('Rejected record counts:', result.get('skipped', {}), flush=True)
    if result['status'] != 'AVAILABLE':
        print('WARNING:', result['message'], flush=True)
        if 'schema_diagnostic' in result:
            print('SCHEMA_DIAGNOSTIC:', json.dumps(result['schema_diagnostic']), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
