import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_ionosphere import (integrate, diagnose, farthest_points,
    sensitivity_factor, great_circle_km, even_indices, build)


class FakeVar:
    def __init__(self, values, attrs=None):
        self.values = values
        self.attrs = attrs or {'units':'m^-3'}
        self.dims = ('alt_km',)
        self.ndim = 1
    def squeeze(self): return self


class FakeCoord:
    def __init__(self, values): self.values = values


class TestsV07(unittest.TestCase):
    def fake_iri(self, t, alt_range, lat, lon):
        alt = list(range(100,2001,25))
        ne = [2e10 + 8e11 * pow(2.718281828,-.5*((h-300)/120)**2) for h in alt]
        return {'ne':FakeVar(ne), 'alt_km':FakeCoord(alt)}

    def test_integral_and_peak(self):
        self.assertAlmostEqual(integrate([100,200],[1e11,1e11]),1.0)
        self.assertEqual(diagnose([180,220,260,300,340],[1e10,2e11,1e12,8e11,2e11])['hmf2_km'],260)

    def test_worldwide_sampling_not_row_major(self):
        cells=[{'lat':lat,'lon':lon,'vtec_tecu':25} for lat in range(-80,81,20) for lon in range(-170,171,20)]
        chosen=farthest_points(cells,36)
        self.assertGreater(max(x[0] for x in chosen),40)
        self.assertLess(min(x[0] for x in chosen),-40)
        self.assertGreater(max(x[1] for x in chosen),90)
        self.assertLess(min(x[1] for x in chosen),-90)
        self.assertAlmostEqual(great_circle_km((0,180),(0,-180)),0,places=5)

    def test_sensitivity_limits(self):
        self.assertEqual(sensitivity_factor(25,20,.01)[0],1.25)
        self.assertIsNone(sensitivity_factor(100,20,.01)[0])
        self.assertIsNone(sensitivity_factor(25,20,.25)[0])
        self.assertEqual(even_indices(10,3),[0,4,9])

    def test_builder_with_fake_iri(self):
        frames=[]
        for i in range(3):
            frames.append({'valid_at':f'2026-11-21T0{i}:00:00Z', 'cells':[
                {'lat':lat,'lon':lon,'vtec_tecu':30.0}
                for lat in (-60,-30,0,30,60) for lon in (-120,-60,0,60,120)]})
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'swift_tec_vtec.json';output=Path(td)/'ionosphere.json'
            source.write_text(json.dumps({'metadata':{'is_forecast':True},'frames':frames}))
            data=build(source,output,12,2,iri_function=self.fake_iri)
            self.assertEqual(len(data['frames']),2)
            self.assertEqual(len(data['frames'][0]['map_cells']),25)
            self.assertEqual(len(data['frames'][0]['cells']),12)
            self.assertEqual(len(data['frames'][0]['cells'][0]['profile']['alt_km']),77)
            self.assertEqual(data['metadata']['is_forecast'],False)
            self.assertGreater(data['frames'][0]['stats']['interpolated_points'],0)
            self.assertTrue(output.exists())


if __name__=='__main__': unittest.main()
