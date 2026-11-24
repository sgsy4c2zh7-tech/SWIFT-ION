"""Offline validation of the actual same-run NOAA Kp feed for the Japan bridge."""
import json
import sys
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from japan_kp_issue import verified_slots

UTC=timezone.utc
NOW=datetime(2026,11,24,5,30,tzinfo=UTC)
START=datetime(2026,11,24,tzinfo=UTC)

def issue():
    return {
        'schema':'swift-ion-swifttec-issue-kp3day-v1',
        'source_mode':'SWIFTTEC_SAME_ISSUE_NOAA_3DAY',
        'generated_at':NOW.isoformat(),
        'valid_from_utc':START.isoformat(),
        'valid_until_exclusive_utc':(START+timedelta(days=3)).isoformat(),
        'slots':[{'valid_from_utc':(START+i*timedelta(hours=3)).isoformat(),
                  'kp':float(i%9)} for i in range(24)]
    }

class KpIssueTests(unittest.TestCase):
    def check(self,data,valid):
        with tempfile.TemporaryDirectory() as p:
            file=Path(p)/'kp.json';file.write_text(json.dumps(data),encoding='utf-8')
            if valid:
                self.assertEqual(len(verified_slots(file,now=NOW)),24)
            else:
                with self.assertRaises(ValueError):verified_slots(file,now=NOW)

    def test_valid_issue(self):self.check(issue(),True)
    def test_reject_unverified(self):
        d=issue();d['source_mode']='UNVERIFIED_NOAA_KP_PROVENANCE';self.check(d,False)
    def test_missing_kp_slot(self):
        d=issue();d['slots'].pop(7);self.check(d,False)
    def test_duplicated_slot(self):
        d=issue();d['slots'][7]=d['slots'][6];self.check(d,False)
    def test_out_of_range_kp(self):
        d=issue();d['slots'][4]['kp']=9.1;self.check(d,False)
    def test_stale_issue(self):
        d=issue();d['generated_at']=(NOW-timedelta(hours=5)).isoformat();self.check(d,False)
    def test_missing_provenance(self):
        d=issue();d['schema']='other';self.check(d,False)

if __name__=='__main__':unittest.main()
