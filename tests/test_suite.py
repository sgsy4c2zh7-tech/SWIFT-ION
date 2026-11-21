import sys,unittest,tempfile,json
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_density_slices import profile_at,distance,slice_frame,build
from build_space_weather import extract,build as build_sw

class SuiteTests(unittest.TestCase):
    def test_profile_linear(self):
        x={'alt_km':[100,200,300],'ne_m3':[1e10,3e10,1e10]}
        self.assertEqual(profile_at(x,150),2e10)
        self.assertIsNone(profile_at(x,99))
    def test_distance_wrap(self):
        self.assertAlmostEqual(distance((0,-179),(0,181)),0)
    def test_slice_frame(self):
        f={'valid_at':'2026-11-21T00:00:00Z',
           'cells':[{'lat':0,'lon':0,'profile':{'alt_km':[100,1100],'ne_m3':[1e11,1e11]}}],
           'map_cells':[{'lat':0,'lon':0},{'lat':10,'lon':20}]}
        x=slice_frame(f,heights=(150,300))
        self.assertEqual(len(x['values_log10_ne_m3']),2)
        self.assertAlmostEqual(x['values_log10_ne_m3'][0][0],11)
    def test_density_export(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'in.json';out=Path(d)/'out.json'
            f={'valid_at':'2026-11-21T00:00:00Z','cells':[{'lat':0,'lon':0,'profile':{'alt_km':[100,2000],'ne_m3':[1e11,1e11]}}],
               'map_cells':[{'lat':0,'lon':0}]}
            source.write_text(json.dumps({'metadata':{'is_forecast':False},'frames':[f,f]}))
            result=build(source,out)
            self.assertEqual(result['schema'],'swift-ion-iri-slices-v1')
    def test_noaa_current(self):
        x=extract({'0':{'G':{'Scale':'2'},'S':{'Scale':'0'},'R':{'Scale':'1'},'DateStamp':'2026-11-21','TimeStamp':'03:00:00'}},'2026-11-21T03:01:00Z')
        self.assertEqual(x['current_scales']['G'],2)
    def test_noaa_failure_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            r=build_sw(Path(d)/'x.json',fetch=lambda:{'0':{}})
            self.assertEqual(r['status'],'unavailable')
if __name__=='__main__':unittest.main()
