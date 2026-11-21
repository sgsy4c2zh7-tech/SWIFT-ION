import unittest, tempfile, json
from pathlib import Path
from src.core.layers import describe_layers,integrated_tec_tecu
from src.gnss.delay import ionospheric_group_delay_m
from src.hf.assessment import assess_route
from src.ingestion.swift_tec import load_export
class Tests(unittest.TestCase):
    def test_layers(self):
        d=describe_layers([70,110,180,300],[1e8,1e10,1e11,1e12])
        self.assertEqual(d['F2']['band_max_altitude_km'],300)
        self.assertFalse(d['F2']['peak_confirmed'])
    def test_integral(self):
        self.assertAlmostEqual(integrated_tec_tecu([100,200],[1e11,1e11]),1)
    def test_bad(self):
        with self.assertRaises(ValueError):describe_layers([200,100],[1,2])
    def test_gnss(self):
        self.assertAlmostEqual(ionospheric_group_delay_m(10,1575.42e6),1.6237,places=3)
    def test_hf_no_invented_freq(self):
        self.assertIsNone(assess_route([{},{}])['fot_mhz'])
    def test_input(self):
        obj={'schema_version':'swift-ion-tec-v1','source':'SWIFT-TEC','issued_at':'2026-11-21T00:00:00Z','valid_at':'2026-11-21T01:00:00Z','cells':[{'lat':35,'lon':140,'vtec_tecu':18}]}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.json';p.write_text(json.dumps(obj));self.assertEqual(len(load_export(p)['cells']),1)
if __name__=='__main__':unittest.main()
