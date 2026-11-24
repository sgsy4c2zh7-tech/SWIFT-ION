"""Deterministic, geographically balanced sampling of available ionosondes.

This module only reorders/chooses measured stations supplied by the upstream
KC2G/GIRO feed. It never invents stations or observations and never considers
observed foF2/hmF2 values while choosing spatial positions.
"""
from __future__ import annotations
import math
from collections import Counter

TARGET_STATIONS = 32
LATITUDE_BANDS = ("south_30_to_90", "equatorial_30S_to_30N", "north_30_to_90")
LONGITUDE_BANDS = ("180W_to_120W", "120W_to_60W", "60W_to_0", "0_to_60E", "60E_to_120E", "120E_to_180E")


def geographic_bin(rec):
    lat = float(rec["lat"])
    lon = ((float(rec["lon"]) + 180) % 360) - 180
    if not -90 <= lat <= 90:
        raise ValueError("Invalid latitude")
    latitude_band = 0 if lat < -30 else 1 if lat < 30 else 2
    longitude_band = min(5, max(0, int((lon + 180) // 60)))
    return (latitude_band, longitude_band)


def distance_km(a, b):
    p1, p2 = math.radians(float(a["lat"])), math.radians(float(b["lat"]))
    dp = p1 - p2
    dl = math.radians(float(a["lon"]) - float(b["lon"]))
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 12742 * math.asin(min(1.0, math.sqrt(max(0.0, h))))


def _station_key(rec):
    return (str(rec.get("station", "")), float(rec["lat"]), float(rec["lon"]))


def balanced_global_sample(records, limit=TARGET_STATIONS):
    """Cover as many *occupied* 30-degree lat/60-degree lon regions as possible.

    The source catalog is not uniformly global. Missing regions remain empty.
    Prefer records with an established confidence score: unknown-confidence
    observations do not qualify for the strict headline skill metric.
    """
    if limit < 1 or not records:
        return []
    pool = []
    seen = set()
    for r in sorted(records, key=_station_key):
        try:
            if not (-90 <= float(r["lat"]) <= 90):
                continue
            geographic_bin(r)
            key = _station_key(r)
        except (KeyError, ValueError, TypeError):
            continue
        if key not in seen:
            seen.add(key)
            pool.append(r)
    selected = []
    # First choose across geographic bins, avoiding densely observed regions.
    # Between equally eligible bins choose farthest from the current sample.
    available = set(range(len(pool)))
    covered_bins = set()
    while available and len(selected) < limit:
        choices = [i for i in available if geographic_bin(pool[i]) not in covered_bins]
        if not choices:
            choices = list(available)
        if selected:
            score = lambda i: min(distance_km(pool[i], pool[j]) for j in selected)
        else:
            # Stable first station near (0,0), as in the previous implementation.
            zero = {"lat": 0, "lon": 0}
            score = lambda i: -distance_km(pool[i], zero)
        # Prefer confidence-known stations only as a *tie breaker*; geographic
        # coverage remains first. This selection does not touch observed values.
        i = max(choices, key=lambda j: (
            bool(pool[j].get("confidence_known", True)),
            score(j),
            -j,
        ))
        selected.append(i)
        available.remove(i)
        covered_bins.add(geographic_bin(pool[i]))
    return [pool[i] for i in selected]


def coverage_summary(eligible_records, selected_records, *, evaluated_records=None):
    def count_bins(records):
        counts = Counter(geographic_bin(r) for r in records)
        return [[counts.get((la, lo), 0) for lo in range(6)] for la in range(3)]
    a = count_bins(eligible_records)
    b = count_bins(selected_records)
    summary = {
        "source_usable_stations": len(eligible_records),
        "selected_stations": len(selected_records),
        "maximum_requested": TARGET_STATIONS,
        "source_occupied_regions": sum(c > 0 for row in a for c in row),
        "selected_occupied_regions": sum(c > 0 for row in b for c in row),
        "latitude_band_labels": list(LATITUDE_BANDS),
        "longitude_band_labels": list(LONGITUDE_BANDS),
        "source_latitude_longitude_counts": a,
        "selected_latitude_longitude_counts": b,
        "selected_confidence_known": sum(r.get("confidence_known") is True for r in selected_records),
        "note": "Geographic bins are not observation grids. Empty bins may mean the KC2G feed has no eligible stations; no coordinates or observations are fabricated.",
    }
    if evaluated_records is not None:
        summary["iri_comparisons_succeeded"] = len(evaluated_records)
    return summary
