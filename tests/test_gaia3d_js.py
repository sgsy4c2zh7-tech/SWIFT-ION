"""Run the numerical JS test suite in GitHub Actions when Node is available."""
import shutil
import subprocess
import unittest
from pathlib import Path


class Gaia3dJsTests(unittest.TestCase):
    def test_geometry_and_model_interpolation(self):
        node = shutil.which('node')
        if node is None:
            self.skipTest('Node.js not on this runner')
        suite = Path(__file__).with_name('test-gaia3d.mjs')
        proc = subprocess.run([node, '--test', str(suite)], capture_output=True,
                              text=True, timeout=40, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + '\n' + proc.stderr)


if __name__ == '__main__':
    unittest.main()
