"""Ensure JS route interpolation and missing-data semantics work on CI."""
import shutil
import subprocess
import unittest
from pathlib import Path

class RouteForecastJSTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'node is not installed')
    def test_route_forecast_js(self):
        path=Path(__file__).with_name('test-route-forecast.mjs')
        result=subprocess.run(['node',str(path)], capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('assertions OK',result.stdout)
