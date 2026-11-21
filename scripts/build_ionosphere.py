"""IRI climatology + SWIFT-TEC comparison and explicit TEC sensitivity scenario.

This DOES NOT assimilate VTEC into a validated 3-D forecast. It computes sparse
IRI reference profiles, geographical interpolations and a separately labelled
uniform-density scaling scenario, leaving hmF2 unchanged.
"""
from __future__ import annotations
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALT_RANGE = [100, 2000, 25]  # covers an ionospheric column, NOT the entire plasmasphere
EARTH_RADIUS_KM = 6371.0
MIN_FACTOR, MAX_FACTOR = 0.5, 2.0


def integrate(alt, ne):
    if len(alt) != len(ne) or len(alt) < 2:
        raise ValueError('IRI altitude/density lengths differ or are too short')
    if any(b <= a for a, b in zip(alt, alt[1:])):
        raise ValueError('Altitudes must strictly increase')
    if any(not math.isfinite(float(x)) or float(x) < 0 for x in ne):
        raise ValueError('Invalid electron density')
    return sum((b - a) * 1000 * (x + y) / 2 for a, b, x, y in zip(alt, alt[1:], ne, ne[1:])) / 1e16


def diagnose(alt, ne):
    """A F2-band sampled maximum; not independently confirmed by ionosonde."""
    eligible = [(float(h), float(n)) for h, n in zip(alt, ne) if 180 <= h <= 600]
    if not eligible:
        raise ValueError('No samples in F2 diagnostic band')
    hm, nm = max(eligible, key=lambda x: x[1])
    return {'nmf2_m3': round(nm, 2), 'hmf2_km': hm,
            'fof2_mhz': round(8.98 * math.sqrt(nm) / 1e6, 3),
            'peak_at_boundary': hm in (eligible[0][0], eligible[-1][0]),
            'peak_type': 'IRI_F2_BAND_SAMPLED_MAX_UNCONFIRMED'}


def extract_iri_profile(dataset):
    if 'ne' not in dataset:
        raise ValueError('iri2020 returned no ne variable')
    value = dataset['ne'].squeeze()
    if value.ndim != 1 or len(value.dims) != 1:
        raise ValueError('Expected one-dimensional IRI profile')
    dim = value.dims[0]
    if dim not in ('alt_km', 'altitude', 'alt'):
        raise ValueError(f'Unexpected IRI altitude dimension: {dim}')
    alt = [float(v) for v in dataset[dim].values]
    ne = [float(v) for v in value.values]
    units = str(value.attrs.get('units', value.attrs.get('unit', ''))).replace(' ', '').lower()
    if units in ('cm^-3', 'cm-3', '1/cm3', 'cm**-3'):
        ne = [v * 1e6 for v in ne]
    elif units not in ('', 'm^-3', 'm-3', '1/m3', 'm**-3'):
        raise ValueError(f'Unrecognised electron-density units: {units}')
    if any(not math.isfinite(h) for h in alt):
        raise ValueError('Nonfinite altitude')
    if not ne or min(ne) < 0 or any(not math.isfinite(v) for v in ne):
        raise ValueError('Invalid electron density')
    if not 1e7 <= max(ne) <= 1e14:
        raise ValueError('Density outside expected m^-3 range; check IRI units')
    integrate(alt, ne)
    return alt, ne


def _coord(cell):
    lat, lon = float(cell['lat']), float(cell['lon'])
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Invalid coordinate')
    return lat, lon


def great_circle_km(a, b):
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    z = math.sin(lat1) * math.sin(lat2) + math.cos(lat1) * math.cos(lat2) * math.cos(lon1-lon2)
    return EARTH_RADIUS_KM * math.acos(max(-1.0, min(1.0, z)))


def farthest_points(cells, count):
    """Deterministic worldwide stratification, not first-N row-major sampling."""
    unique = {}
    for cell in cells:
        try:
            pt = _coord(cell)
            tec = float(cell['vtec_tecu'])
            if math.isfinite(tec) and 0 <= tec <= 200:
                unique[pt] = cell
        except (KeyError, TypeError, ValueError):
            continue
    pts = sorted(unique)
    if not pts:
        raise ValueError('No valid SWIFT-TEC grid cells')
    count = min(max(1, int(count)), len(pts))
    first = min(range(len(pts)), key=lambda i: great_circle_km((0, 0), pts[i]))
    chosen = [first]
    remaining = set(range(len(pts))) - {first}
    min_dist = [great_circle_km(pts[i], pts[first]) for i in range(len(pts))]
    while len(chosen) < count:
        next_idx = max(remaining, key=lambda i: (min_dist[i], -i))
        chosen.append(next_idx)
        remaining.remove(next_idx)
        for i in remaining:
            min_dist[i] = min(min_dist[i], great_circle_km(pts[i], pts[next_idx]))
    return [pts[i] for i in chosen]


def sensitivity_factor(tec_forecast, iri_100_2000_tecu, top_to_peak_ratio):
    """Conservative what-if scenario; missing external plasmasphere is NOT corrected.

    Rejection avoids extrapolating near-empty or strongly truncated IRI profiles.
    """
    if iri_100_2000_tecu <= 0 or top_to_peak_ratio > 0.10:
        return None, 'iri_topside_truncated_or_zero'
    factor = tec_forecast / iri_100_2000_tecu
    if not (MIN_FACTOR <= factor <= MAX_FACTOR):
        return None, 'large_tec_discrepancy_outside_sensitivity_bounds'
    return factor, 'hypothetical_uniform_scaling_100_2000km'


def build_model_cell(IRI, valid_at, source_cell):
    lat, lon = _coord(source_cell)
    vtec = float(source_cell['vtec_tecu'])
    ds = IRI(valid_at, ALT_RANGE, lat, lon)
    alt, ne = extract_iri_profile(ds)
    part = integrate(alt, ne)
    diag = diagnose(alt, ne)
    factor, reason = sensitivity_factor(vtec, part, ne[-1] / max(ne))
    scenario = None
    scaled = None
    if factor is not None:
        scaled = [round(v * factor, 3) for v in ne]
        scenario = diagnose(alt, scaled)
    return {'lat': lat, 'lon': lon, 'vtec_swifttec_tecu': round(vtec, 3),
            'iri_partial_tec_100_2000_tecu': round(part, 3),
            'iri': diag, 'tec_scenario': scenario,
            'scenario_factor': None if factor is None else round(factor, 5),
            'scenario_status': reason,
            'top_to_peak_density_ratio': round(ne[-1]/max(ne), 5),
            'profile': {'alt_km': alt, 'ne_m3': [round(v, 3) for v in ne],
                        'ne_m3_tec_scenario': scaled}}


def interpolate_cell(lat, lon, sample_cells, swift_tec):
    """IDW of sparse *model diagnostics*, not a fresh IRI computation."""
    by_dist = sorted(((great_circle_km((lat, lon), (s['lat'], s['lon'])), s)
                      for s in sample_cells), key=lambda p: p[0])[:5]
    nearest = by_dist[0][0]
    if nearest < 1.0:
        s = by_dist[0][1]
        return {'lat': lat, 'lon': lon, 'vtec_swifttec_tecu': swift_tec,
                'iri': s['iri'], 'tec_scenario': s['tec_scenario'],
                'method': 'IRI_RUN', 'nearest_iri_km': 0}
    weights = [1.0 / max(dist, 50.0) ** 2 for dist, _ in by_dist]
    def metric(group, key):
        selected = [(w, s[group][key]) for w, (_, s) in zip(weights, by_dist)
                    if s.get(group) and math.isfinite(float(s[group].get(key, float('nan'))))]
        if not selected:
            return None
        return sum(w*v for w,v in selected) / sum(w for w,_ in selected)
    nm, hm = metric('iri','nmf2_m3'), metric('iri','hmf2_km')
    sc_nm, sc_hm = metric('tec_scenario','nmf2_m3'), metric('tec_scenario','hmf2_km')
    iri = {'nmf2_m3': round(nm,2), 'hmf2_km': round(hm,2),
           'fof2_mhz': round(8.98 * math.sqrt(nm) / 1e6,3)}
    scenario = None if sc_nm is None else {'nmf2_m3': round(sc_nm,2),
        'hmf2_km': round(sc_hm,2), 'fof2_mhz': round(8.98*math.sqrt(sc_nm)/1e6,3)}
    return {'lat': lat, 'lon': lon, 'vtec_swifttec_tecu': swift_tec,
            'iri': iri, 'tec_scenario': scenario,
            'method': 'SPATIAL_INTERPOLATION', 'nearest_iri_km': round(nearest, 1)}


def even_indices(total, max_frames):
    n = min(total, max(1, max_frames))
    if n == 1:
        return [0]
    return sorted(set(round(i*(total-1)/(n-1)) for i in range(n)))


def build(input_path, output_path, max_cells=72, max_frames=3, iri_function=None):
    if iri_function is None:
        from iri2020 import IRI as iri_function
    raw = json.loads(Path(input_path).read_text(encoding='utf-8'))
    if raw.get('metadata', {}).get('is_forecast') is not True:
        raise ValueError('SWIFT-TEC source is not labeled forecast')
    frames_in = raw.get('frames', [])
    if not frames_in:
        raise ValueError('SWIFT-TEC contains no forecast frames')
    selected_coords = farthest_points(frames_in[0]['cells'], max_cells)
    output_frames, errors = [], []
    for frame_idx in even_indices(len(frames_in), max_frames):
        frame = frames_in[frame_idx]
        ts = frame['valid_at']
        valid = datetime.fromisoformat(ts.replace('Z','+00:00'))
        if valid.tzinfo is None:
            raise ValueError('Forecast valid_at must have timezone')
        indexed = {}
        for c in frame['cells']:
            try: indexed[_coord(c)] = c
            except (ValueError, KeyError, TypeError): continue
        cells = []
        for lat, lon in selected_coords:
            source = indexed.get((lat, lon))
            if source is None: continue
            try:
                cells.append(build_model_cell(iri_function, valid, source))
            except Exception as ex:
                errors.append({'time':ts,'lat':lat,'lon':lon,'error':str(ex)[:180]})
        if len(cells) < max(8, math.ceil(len(selected_coords)*0.75)):
            raise RuntimeError(f'Insufficient valid IRI profiles: {len(cells)}/{len(selected_coords)}; first errors: {errors[:3]}')
        mapped = []
        for item in frame['cells']:
            try:
                lat, lon = _coord(item)
                value = float(item['vtec_tecu'])
                if math.isfinite(value) and 0 <= value <= 200:
                    mapped.append(interpolate_cell(lat, lon, cells, value))
            except (ValueError, TypeError, KeyError):
                pass
        if len(mapped) < len(cells):
            raise ValueError('Map contained fewer points than IRI samples')
        output_frames.append({'valid_at':ts, 'cells':cells, 'map_cells':mapped,
                'stats':{'iri_computations':len(cells),'map_points':len(mapped),
                         'interpolated_points':sum(c['method']=='SPATIAL_INTERPOLATION' for c in mapped),
                         'tec_scenarios_accepted':sum(c['tec_scenario'] is not None for c in cells)}})
        print(f'IRI {ts}: computed {len(cells)} sites; mapped {len(mapped)} locations',flush=True)
    payload = {'metadata':{
        'kind':'IRI_CLIMATOLOGY_AND_EXPERIMENTAL_TEC_SENSITIVITY',
        'is_forecast':False, 'is_observation':False,
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'iri_model':'iri2020', 'iri_altitude_km':ALT_RANGE,
        'source_tec':'SWIFT-TEC runForecast (read-only)',
        'source_stage':raw.get('metadata',{}).get('source_stage','unverified'),
        'sampled_iri_locations':len(selected_coords),
        'warning':'IRI climatological model and spatial interpolation, NOT validated density forecasts. TEC scaling is a hypothetical 100–2000 km column sensitivity: plasmasphere/out-of-range TEC are omitted; no independent hmF2 correction. D-region excluded.',
        'scaling_assumption':'Assume measured/modelled full VTEC approximately represented by IRI 100–2000 km partial TEC; deliberately imperfect. Applies only when ratio in [0.5,2] and negligible boundary density.',
        'model_failures':len(errors), 'error_samples':errors[:10],
        }, 'frames':output_frames}
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8')
    tmp.replace(output_path)
    print(f'Wrote {output_path} ({len(output_frames)} frames, {len(selected_coords)} selected IRI locations)')
    return payload


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,default=ROOT/'docs/swift_tec_vtec.json')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/ionosphere.json')
    parser.add_argument('--max-cells',type=int,default=72)
    parser.add_argument('--max-frames',type=int,default=3)
    args=parser.parse_args()
    build(args.input,args.output,args.max_cells,args.max_frames)
