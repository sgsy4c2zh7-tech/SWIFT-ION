"""Attach NOAA SWPC estimated *observed* 3-hour Kp to already-issued foF2 verification pairs.

This module MUST NOT be used when generating predictions. It only labels a
previously issued forecast *after* the observation's three-hour bin has ended.
The original kp_forecast and kp_3day_confirmed are never changed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import math

from build_year_archive import dates, read_daily, write_daily
from build_prospective_skill import parse_utc

NOAA_SOURCE = "NOAA SWPC estimated observed planetary Kp (3-hour)"
DEFAULT_UPSTREAM = Path("_upstream_swifttec/docs/data/ai/isee_japan/kp_actual_archive.json")


def load_noaa_observed_kp(path=DEFAULT_UPSTREAM):
    """Read SWIFT-TEC's archived NOAA observations, not its forecast Kp.

    Returns UTC-interval-start => (Kp, source). Missing or invalid archive is
    empty; no replacement with predicted Kp, 3, or an interpolation is allowed.
    """
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return {}
    if not isinstance(obj, dict) or obj.get("source") != "NOAA SWPC planetary K-index":
        return {}
    out = {}
    for record in obj.get("rows", []):
        if not isinstance(record, dict):
            continue
        try:
            stamp = parse_utc(record["time_utc"])
            if stamp.tzinfo is None:
                continue
            stamp = stamp.astimezone(timezone.utc)
            value = float(record["kp"])
            if not math.isfinite(value) or not (0 <= value <= 9):
                continue
            if stamp.minute != 0 or stamp.second != 0 or stamp.hour % 3 != 0:
                continue
            out[stamp] = value
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return out


def observed_kp_for_target(valid_at, now, kp_by_start):
    """Exact 3-hour UTC bin match only; never nearest Kp or future-looking value."""
    try:
        target = parse_utc(valid_at).astimezone(timezone.utc)
        stamp = target.replace(hour=(target.hour // 3) * 3, minute=0, second=0, microsecond=0)
        if now.astimezone(timezone.utc) < stamp + timedelta(hours=3):
            return None, None
        return (kp_by_start[stamp], stamp) if stamp in kp_by_start else (None, None)
    except (TypeError, ValueError, AttributeError, KeyError):
        return None, None


def backfill_verified_matches(history, now, archive_path=DEFAULT_UPSTREAM):
    """Persist Kp labels on scored pairs, retaining them for 365 days.

    Existing Kp labels are not deleted when the source is briefly missing.
    Reading archived Kp never modifies a forecast or a predictive feature.
    Only rewritten dates with newly attached Kp data change on disk.
    """
    kp_rows = load_noaa_observed_kp(archive_path)
    if not kp_rows:
        return {"source": NOAA_SOURCE, "source_slots": 0, "tagged": 0, "changed_days": 0}
    first = min(kp_rows).date()
    from_day = max(first, now.date() - timedelta(days=365))
    changed_days = tagged = 0
    for day in dates(from_day, now.date()):
        existing = read_daily(Path(history) / "tec_matches", day)
        if not existing:
            continue
        changed = False
        for match in existing:
            if not isinstance(match, dict):
                continue
            old = match.get("kp_observed")
            if type(old) in (int, float) and math.isfinite(old) and 0 <= old <= 9:
                continue
            kp, slot = observed_kp_for_target(match.get("valid_at"), now, kp_rows)
            if kp is None:
                continue
            # Records must have been issued before their verification target.
            try:
                if parse_utc(match["issued_at"]) >= parse_utc(match["valid_at"]):
                    continue
            except (KeyError, ValueError, TypeError):
                continue
            match["kp_observed"] = round(kp, 3)
            match["kp_observed_slot_utc"] = slot.isoformat().replace("+00:00", "Z")
            match["kp_observed_source"] = NOAA_SOURCE
            tagged += 1
            changed = True
        if changed:
            write_daily(Path(history) / "tec_matches", day, existing)
            changed_days += 1
    return {"source": NOAA_SOURCE, "source_slots": len(kp_rows), "tagged": tagged, "changed_days": changed_days}
