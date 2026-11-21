"""Prospective IRI + SWIFT-TEC scenario: deterministic mock-only tests."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import json,math,sys,tempfile,unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_ion_forecast as m

class TestIonosphereForecast(unittest.TestCase):
    @staticmethod
    def provider(t,lat,lon):
        alts=m.PROFILE_ALTITUDES
        ne=[1e9+1.1e12*math.exp(-((h-320)/145)**2)*(1+0.03*math.cos(math.radians(lat))) for h in alts]
        return alts,ne

    def test_peak_and_iri_tec_math(self):
        a,ne=self.provider(None,35,139)
        peak=m.f2_peak(ne)
        self.assertTrue(8<peak['fof2_mhz']<11)
        self.assertEqual(peak['hmf2_km'],325)
        partial=m.integral_tec(ne)
        self.assertGreater(partial,10)
        f,st,_=m.scenario(ne,partial*1.21)
        self.assertEqual(st,'SCENARIO_AVAILABLE')
        self.assertAlmostEqual(f,1.21,places=3)
        self.assertAlmostEqual(peak['fof2_mhz']*math.sqrt(f),peak['fof2_mhz']*1.1)

    def test_out_of_range_tec_rejected(self):
        ne=self.provider(None,35,139)[1]
        f,st,_=m.scenario(ne,5*m.integral_tec(ne))
        self.assertIsNone(f)
        self.assertEqual(st,'VTEC_PARTIAL_TEC_MISMATCH')

    def test_grid_missing_and_bilinear(self):
        lat=[30,40];lon=[130,140]
        self.assertAlmostEqual(m.bilinear_vtec([100,200,300,400],lat,lon,35,135),25)
        self.assertIsNone(m.bilinear_vtec([100,None,300,400],lat,lon,35,135))
        self.assertIsNone(m.bilinear_vtec([100,200,300,400],lat,lon,50,135))

    def test_model_output_uses_exact_forecast_times(self):
        t0=datetime(2026,11,21,tzinfo=timezone.utc)
        ts=[m.iso(t0+timedelta(minutes=30*i)) for i in range(7)]
        lat=[-90,0,35,45,90];lon=[-170,0,130,140,170]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);anim=root/'animation';anim.mkdir();
            idx={'schema':'swift-ion-vtec-animation-v1','metadata':{'is_forecast':True,'units':'TECU','time_step_minutes':30,'value_scale':10,'generated_at':m.iso(t0),'source_stage':'test'},
                 'time_utc':ts,'latitudes':lat,'longitudes':lon,'chunks':[{'file':'frames_000.json','count':len(ts),'start':0}]}
            (anim/'index.json').write_text(json.dumps(idx))
            (anim/'frames_000.json').write_text(json.dumps({'start':0,'values':[[175]*25 for _ in ts]}))
            ion={'metadata':{'is_forecast':False},'frames':[{'cells':[{'lat':-30,'lon':-50},{'lat':30,'lon':60},{'lat':60,'lon':-80},{'lat':0,'lon':0}]}]}
            src=root/'ionosphere.json';src.write_text(json.dumps(ion))
            output=root/'out.json'
            data=m.build(anim,src,output,now=t0+timedelta(minutes=15),iri_provider=self.provider,max_sites=8,anchor_hours=1)
            self.assertEqual(data['status'],'AVAILABLE')
            self.assertEqual(len(data['frames']),7)
            self.assertEqual([f['valid_at'] for f in data['frames']],ts)
            self.assertFalse(data['frames'][0]['is_prospective'])
            self.assertTrue(data['frames'][-1]['is_prospective'])
            self.assertFalse(data['metadata']['is_validated_forecast'])
            self.assertTrue(data['metadata']['hmf2_is_iri_only'])
            self.assertTrue(output.exists())
            for frame in data['frames']:
                for site in frame['sites']:
                    self.assertEqual(site['hmf2_iri_km'],site['hmf2_tec_km'] if site['factor'] else site['hmf2_iri_km'])
                    if site['factor'] is None:
                        self.assertTrue(all(x is None for x in site['tec_ne_log10_m3']))

    def test_missing_records_never_filled(self):
        ne=self.provider(None,25,130)[1]
        f,st,_=m.scenario(ne,None)
        self.assertIsNone(f);self.assertEqual(st,'VTEC_MISSING')

if __name__=='__main__':unittest.main()
