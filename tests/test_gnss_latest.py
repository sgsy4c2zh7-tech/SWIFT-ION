import json
import tempfile
import unittest
from pathlib import Path
from scripts.build_gnss_latest import read_tle, build

LINE1='1 26407U 00040A   26327.02605608  .00000071  00000+0  00000+0 0  9996'
LINE2='2 26407  54.8237 208.8598 0114376 305.3106 185.6133  2.00559057193137'

class GNSSLatestTest(unittest.TestCase):
    def test_tle_health_and_dedupe(self):
        records=read_tle('\n'.join(['GPS PRN 22',LINE1,LINE2,'GPS PRN 22',LINE1,LINE2]),'gps',{'22':0})
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['health'],0)
    def test_snapshot_overwrites_instead_of_archiving(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            gnss=base/'up'/'docs'/'data'/'gnss';gnss.mkdir(parents=True)
            (gnss/'gps_latest.tle').write_text('\n'.join(['GPS PRN 22',LINE1,LINE2])+'\n')
            vendor=base/'up'/'docs'/'vendor';vendor.mkdir()
            (vendor/'satellite.min.js').write_text('demo')
            output=base/'site'/'gnss_latest.json'
            for n in (1,2):
                build(base/'up',output,base/'site'/'vendor'/'satellite.min.js')
                self.assertEqual(len(list(output.parent.glob('gnss*'))),1)
            info=json.loads(output.read_text())
            self.assertTrue(info['is_latest_only'])
            self.assertFalse(info['historical_tle_retained'])
            self.assertEqual(info['satellite_counts']['gps'],1)

if __name__=='__main__':unittest.main()
