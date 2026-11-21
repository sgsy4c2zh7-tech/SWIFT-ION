import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_ionosphere import integrate, diagnose
class TestIon(unittest.TestCase):
    def test_integral(self):
        self.assertAlmostEqual(integrate([100,200],[1e11,1e11]),1.0)
    def test_fof2(self):
        x=diagnose([180,220,260,300,340],[1e10,2e11,1e12,8e11,2e11])
        self.assertEqual(x['hmf2_km'],260)
        self.assertAlmostEqual(x['fof2_mhz'],8.98)
if __name__=='__main__':unittest.main()
