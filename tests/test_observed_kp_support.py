"""Regression tests: actual geomagnetic activity must never leak into forecast calculation."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from build_year_archive import read_daily, write_daily
from observed_kp_support import (
    load_noaa_observed_kp, observed_kp_for_target, backfill_verified_matches,
    NOAA_SOURCE,
)

UTC = timezone.utc


class ObservedKpTests(unittest.TestCase):
    def test_exact_three_hour_slot_and_no_future_leak(self):
        slot = datetime(2026, 11, 23, 3, tzinfo=UTC)
        series = {slot: 6.0}
        kp, start = observed_kp_for_target('2026-11-23T05:30:00Z', slot + timedelta(hours=3), series)
        self.assertEqual(kp, 6.0)
        self.assertEqual(start, slot)
        self.assertEqual(observed_kp_for_target('2026-11-23T04:00:00Z', slot + timedelta(hours=2), series)[0], None)
        self.assertEqual(observed_kp_for_target('2026-11-23T06:00:00Z', slot + timedelta(hours=4), series)[0], None)

    def test_invalid_source_or_out_of_range_kp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'index.json'
            path.write_text(json.dumps({'source': 'NOAA 3-day FORECAST', 'rows': [
                {'time_utc': '2026-11-23T03:00:00Z', 'kp': 6}
            ]}), encoding='utf-8')
            self.assertEqual(load_noaa_observed_kp(path), {})
            path.write_text(json.dumps({'source': 'NOAA SWPC planetary K-index', 'rows': [
                {'time_utc': '2026-11-23T03:00:00Z', 'kp': 6},
                {'time_utc': '2026-11-23T06:00:00Z', 'kp': 9.1},
                {'time_utc': '2026-11-23T09:30:00Z', 'kp': 5},
            ]}), encoding='utf-8')
            found = load_noaa_observed_kp(path)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[datetime(2026, 11, 23, 3, tzinfo=UTC)], 6)

    def test_backfill_never_changes_issued_forecast_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / 'kp.json'
            archive.write_text(json.dumps({'source': 'NOAA SWPC planetary K-index', 'rows': [
                {'time_utc': '2026-11-23T03:00:00Z', 'kp': 6.0},
            ]}), encoding='utf-8')
            history = root / 'history'
            target = history / 'tec_matches'
            records = [{
                'station': 'TEST', 'issued_at': '2026-11-23T00:30:00Z',
                'valid_at': '2026-11-23T04:00:00Z', 'nominal_horizon_h': 3,
                'kp_forecast': 2.0, 'kp_3day_confirmed': True,
                'predicted_fof2_tec_mhz': 5.5, 'observed_fof2_mhz': 6.0,
            }]
            write_daily(target, datetime(2026,11,23,tzinfo=UTC).date(), records)
            now = datetime(2026,11,23,7,tzinfo=UTC)
            result = backfill_verified_matches(history, now, archive)
            self.assertEqual(result['tagged'], 1)
            updated = read_daily(target, datetime(2026,11,23,tzinfo=UTC).date())[0]
            self.assertEqual(updated['kp_observed'], 6.0)
            self.assertEqual(updated['kp_forecast'], 2.0)
            self.assertEqual(updated['predicted_fof2_tec_mhz'], 5.5)
            self.assertEqual(updated['kp_observed_source'], NOAA_SOURCE)
            self.assertEqual(backfill_verified_matches(history, now, archive)['tagged'], 0)
            archive.unlink()
            self.assertEqual(backfill_verified_matches(history, now, archive)['tagged'], 0)
            self.assertEqual(read_daily(target, datetime(2026,11,23,tzinfo=UTC).date())[0]['kp_observed'], 6.0)

    def test_actual_storm_classification_even_if_forecast_predicted_quiet(self):
        from build_tec_skill import paired_summary
        row = {
            'station': 'TEST', 'issued_at': '2026-11-23T00:30:00Z',
            'valid_at': '2026-11-23T04:00:00Z',
            'fof2_quality': 'STANDARD', 'kp_3day_confirmed': True,
            'kp_forecast': 2.0, 'kp_observed': 6.0,
            'predicted_fof2_iri_mhz': 5.0,
            'predicted_fof2_tec_mhz': 6.0,
            'observed_fof2_mhz': 5.6,
        }
        summary = paired_summary([row])
        self.assertEqual(summary['kp3day_by_observed_activity']['STORM_KP_GE_5']['paired_count'], 1)
        self.assertEqual(summary['kp3day_by_observed_activity']['QUIET_KP_LT_4']['paired_count'], 0)
        self.assertEqual(summary['kp3day_by_activity']['QUIET_KP_LT_4']['paired_count'], 1)
        self.assertEqual(summary['kp3day_by_activity']['STORM_KP_GE_5']['paired_count'], 0)

    def test_patching_is_idempotent_when_existing_source_already_patched(self):
        # Dynamic import avoids applying a migration in the test runner.
        from apply_observed_kp_patch import upgrade_tec, upgrade_year
        source = '... kp3day_by_observed_activity ...'
        self.assertEqual(upgrade_tec(source), source)
        self.assertEqual(upgrade_year(source), source)


if __name__ == '__main__':
    unittest.main()
