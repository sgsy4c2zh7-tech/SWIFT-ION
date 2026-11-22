"""Regression tests for station reservation after actual forecast sampling.

The station list uses only issue-time metadata (station IDs/coordinates), never
observation foF2 values. A candidate must have an issued sampled forecast
before it reserves a name/coordinate.
"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_tec_skill import build_snapshot
from build_prospective_skill import iso

NOW = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)


def forecast(site_coords):
    frames = []
    for h in (1, 3, 6, 12, 24):
        frames.append({'valid_at': iso(NOW + timedelta(hours=h)),
                       'sites': [{'lat': lat, 'lon': lon, 'fof2_iri_mhz': 8.0,
                                  'fof2_tec_mhz': 8.4} for lat, lon in site_coords]})
    return {'schema': 'swift-ion-iri-tec-forecast-v1', 'status': 'AVAILABLE',
            'metadata': {'issued_at': iso(NOW - timedelta(minutes=10))},
            'frames': frames}


class TestIssueTimeStationFallback(unittest.TestCase):
    def test_ni_ct_fixed_remains_primary_when_supported(self):
        fixed = [(45.16, 141.75), (35.71, 139.49),
                 (31.20, 130.62), (26.68, 128.15)]
        snapshot, reason = build_snapshot(forecast(fixed), {'stations': []}, NOW)
        self.assertEqual(reason, 'AVAILABLE')
        self.assertEqual({p['station'] for p in snapshot['forecasts']},
                         {'WAKKANAI', 'KOKUBUNJI', 'YAMAGAWA', 'OKINAWA'})
        self.assertEqual(len(snapshot['forecasts']), 4 * 5)

    def test_fallback_to_issue_time_station_metadata_if_fixed_unsampleable(self):
        # One exactly sampled model site, 25 km from official station;
        # strict sparse-support rule rejects the fixed location, not the site.
        model = forecast([(35.68, 139.76)])
        stations = {'stations': [{'station': 'KOKUBUNJI',
                                  'lat': 35.68, 'lon': 139.76,
                                  'fof2_mhz': 9999}]}
        snapshot, reason = build_snapshot(model, stations, NOW)
        self.assertEqual(reason, 'AVAILABLE')
        self.assertEqual(len(snapshot['forecasts']), 5)
        for row in snapshot['forecasts']:
            self.assertEqual(row['station'], 'KOKUBUNJI')
            self.assertAlmostEqual(row['predicted_fof2_tec_mhz'], 8.4)
            self.assertEqual((row['lat'], row['lon']), (35.68, 139.76))
        # Observation field (even nonsensical 9999) is never used to predict.


if __name__ == '__main__':
    unittest.main()
