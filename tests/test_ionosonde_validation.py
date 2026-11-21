import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_ionosondes import parse_stations, global_sample, error_stats, evaluate

NOW = datetime(2026, 11, 21, 6, 0, tzinfo=timezone.utc)

def record(name, lat, lon, fof2=7.5, hmf2=310, confidence=90, hours_old=1):
    return {'station': {'name': name, 'latitude': str(lat), 'longitude': str(lon)},
            'time': (NOW - timedelta(hours=hours_old)).isoformat(),
            'fof2': fof2, 'hmf2': hmf2, 'cs': confidence}

class IonosondeTests(unittest.TestCase):
    def test_parse_live_kc2g_shape(self):
        stations, skipped = parse_stations([record('A', 35.0, 140.0)], now=NOW)
        self.assertEqual(len(stations), 1)
        self.assertEqual(stations[0]['fof2_mhz'], 7.5)
        self.assertEqual(stations[0]['hmf2_km'], 310)
        self.assertEqual(sum(skipped.values()), 0)

    def test_stale_low_confidence_and_future_excluded(self):
        raw = [record('A', 0, 0, hours_old=10), record('B', 10, 10, confidence=30),
               record('C', -5, -5, hours_old=-3)]
        st, skipped = parse_stations(raw, now=NOW)
        self.assertEqual(st, [])
        self.assertEqual(skipped['stale'], 2)
        self.assertEqual(skipped['low_confidence'], 1)

    def test_nulls_and_unknown_confidence(self):
        st, _ = parse_stations([record('A', 20, 30, fof2=None, hmf2=260, confidence=None)], now=NOW)
        self.assertEqual(len(st), 1)
        self.assertIsNone(st[0]['fof2_mhz'])
        self.assertFalse(st[0]['confidence_known'])

    def test_longitude_wrap_and_duplicate_latest(self):
        raw = [record('A', 10, 350, hours_old=2), record('A', 10, -10, hours_old=1)]
        st, _ = parse_stations(raw, now=NOW)
        self.assertEqual(len(st), 1)
        self.assertEqual(st[0]['lon'], -10)
        self.assertEqual(st[0]['age_hours'], 1)

    def test_stats_sign_and_missing(self):
        x = error_stats([(10, 8), (5, 9)], 'MHz')
        self.assertEqual(x['mae'], 3)
        self.assertEqual(x['bias'], -1)
        self.assertAlmostEqual(x['rmse'], 3.162, places=3)
        self.assertEqual(error_stats([], 'km')['status'], 'NO_MATCHES')

    def test_global_sample_spreads(self):
        st, _ = parse_stations([record('A', 0, 0),record('B', 0, 170),
                                record('C', 60, 0),record('D', -60, 0)], now=NOW)
        sample = global_sample(st, 3)
        self.assertEqual(len(sample), 3)
        self.assertEqual(len(set(r['station'] for r in sample)), 3)

    def test_no_observations_has_no_accuracy(self):
        res = evaluate([], now=NOW)
        self.assertEqual(res['status'], 'NO_USABLE_OBSERVATIONS')
        self.assertEqual(res['metrics']['fof2']['sample_count'], 0)
        self.assertIsNone(res['metrics']['fof2']['mae'])
        self.assertFalse(res['metadata']['is_forecast_skill'])

    def test_reject_unknown_schema(self):
        with self.assertRaises(ValueError):
            parse_stations({'stations': []}, now=NOW)

if __name__ == '__main__': unittest.main()
