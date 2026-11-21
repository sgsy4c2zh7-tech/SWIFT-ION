"""KC2G source-specific UTC-naive compatibility; no silent guessing for others."""
import unittest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from validate_ionosondes import utc, parse_stations, evaluate, schema_diagnostic

NOW = datetime(2026,11,21,6,0,0,tzinfo=timezone.utc)

def station(at, **kwargs):
    r={'station':{'name':'KC2G Example','latitude':'35.0','longitude':'140.0'},
       'time':at,'fof2':7.2,'hmf2':305,'cs':85}
    r.update(kwargs);return r

class TestTimeHandling(unittest.TestCase):
    def test_strict_generic_parser_rejects_naive(self):
        with self.assertRaises(ValueError):utc('2026-11-21T05:30:00')

    def test_kc2g_naive_utc_is_explicit(self):
        dt=utc('2026-11-21T05:30:00',kc2g_naive_utc=True)
        self.assertEqual(dt,datetime(2026,11,21,5,30,tzinfo=timezone.utc))

    def test_live_like_naive_datetime_kept(self):
        rows,sk=parse_stations([station('2026-11-21T05:30:00')],now=NOW)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['observed_at'],'2026-11-21T05:30:00Z')
        self.assertEqual(sum(sk.values()),0)

    def test_explicit_offset_converted_correctly(self):
        rows,sk=parse_stations([station('2026-11-21T14:30:00+09:00')],now=NOW)
        self.assertEqual(rows[0]['observed_at'],'2026-11-21T05:30:00Z')

    def test_stale_still_rejected(self):
        rows,sk=parse_stations([station('2026-11-20T10:00:00')],now=NOW)
        self.assertEqual(rows,[])
        self.assertEqual(sk['stale'],1)

    def test_broken_time_not_bad_shape(self):
        rows,sk=parse_stations([station('not-a-date')],now=NOW)
        self.assertEqual(rows,[])
        self.assertEqual(sk['bad_timestamp'],1)
        self.assertEqual(sk['bad_shape'],0)

    def test_schema_error_exposes_structure_only(self):
        raw=[{'station':'AB123','time':'2026-11-21T05:00:00','fof2':7}]
        r=evaluate(raw,now=NOW)
        self.assertEqual(r['status'],'SOURCE_SCHEMA_ERROR')
        self.assertEqual(r['schema_diagnostic']['station_type'],'str')
        self.assertNotIn('AB123',str(r['schema_diagnostic']))

    def test_no_characteristics_not_fabricated(self):
        rows,sk=parse_stations([station('2026-11-21T05:00:00',fof2=None,hmf2=None)],now=NOW)
        self.assertEqual(rows,[])
        self.assertEqual(sk['no_characteristics'],1)

if __name__=='__main__':unittest.main()
