"""Quality-gated missing-ratio tests with wholly synthetic electron density."""
import math, sys, unittest, tempfile, json
from pathlib import Path
from datetime import datetime, timedelta, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_ion_forecast import PROFILE_ALTITUDES, scenario, extended_scenario, integral_tec, build
from build_tec_skill import sample_station
from build_year_archive import write_daily
from train_fof2_calibration import training_rows
from build_tec_skill import paired_summary
from build_fof2_stage_skill import rollup

class TestContinuousTecFoF2(unittest.TestCase):
    def setUp(self):
        self.ne=[5e9+6e11*math.exp(-((h-310)/95)**2) for h in PROFILE_ALTITUDES]
        self.partial=integral_tec(self.ne)

    def test_standard_values_exactly_preserved(self):
        for ratio in (.5,.8,1,1.5,2):
            old=scenario(self.ne,self.partial*ratio)
            new=extended_scenario(self.ne,self.partial*ratio)
            self.assertEqual(old[0],new[0]);self.assertEqual(new[3],'STANDARD')
            self.assertEqual(new[1],'SCENARIO_AVAILABLE')

    def test_low_tec_ratio_continuity_without_fake_input(self):
        self.assertIsNone(scenario(self.ne,self.partial*.25)[0])
        ratios=[.01,.1,.2,.3,.499,.5,.501,.8]
        f=[extended_scenario(self.ne,self.partial*x)[0] for x in ratios]
        self.assertTrue(all(x is not None for x in f))
        self.assertTrue(all(a<b for a,b in zip(f,f[1:])))
        self.assertGreater(f[0],.35)
        self.assertAlmostEqual(f[3],.35+.15*math.exp(-(.5-.3)/.15))
        self.assertEqual(extended_scenario(self.ne,self.partial*.25)[3],'EXTENDED')

    def test_high_tec_ratio_bounded_and_monotone(self):
        f=[extended_scenario(self.ne,self.partial*x)[0] for x in (2,2.01,3,5,10)]
        self.assertTrue(all(a<b for a,b in zip(f,f[1:])))
        self.assertTrue(all(x<=2.5 for x in f))

    def test_missing_tec_never_imputed(self):
        for v in (None,0,-2):
            a=extended_scenario(self.ne,v)
            self.assertIsNone(a[0]);self.assertEqual(a[3],'MISSING')

    def test_low_confidence_when_topside_is_large(self):
        n=[1e11 + 6e11*math.exp(-((h-310)/100)**2) for h in PROFILE_ALTITUDES]
        partial=integral_tec(n)
        self.assertEqual(scenario(n,partial)[1],'TOPSIDE_TRUNCATION')
        a=extended_scenario(n,partial)
        self.assertEqual(a[3],'EXTENDED')
        self.assertEqual(a[1],'EXTENDED_TOPSIDE')

    def test_station_quality_propagation(self):
        frame={'sites':[{'lat':35,'lon':139,'fof2_iri_mhz':8,
                 'fof2_tec_mhz':7,'fof2_physics_mhz':7,'fof2_quality':'EXTENDED'}]}
        row=sample_station(frame,35,139)
        self.assertIsNotNone(row)
        self.assertEqual(row['fof2_quality'],'EXTENDED')

    def test_exclude_extended_from_learning(self):
        now=datetime(2026,11,23,12,tzinfo=timezone.utc)
        at=now-timedelta(hours=3)
        def iso(t):return t.isoformat().replace('+00:00','Z')
        base={'station':'JP','valid_at':iso(at),'observed_at':iso(now-timedelta(hours=2)),
              'issued_at':iso(at-timedelta(hours=2)),'predicted_fof2_iri_mhz':8,
              'predicted_fof2_physics_mhz':8.2,'observed_fof2_mhz':8.1,'lat':35,'lon':139}
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            write_daily(folder/'tec_matches',at.date(),[dict(base,fof2_quality='EXTENDED')])
            self.assertEqual(training_rows(folder,now),[])
            write_daily(folder/'tec_matches',at.date(),[dict(base,fof2_quality='STANDARD')])
            self.assertEqual(len(training_rows(folder,now)),1)

    def test_main_skill_separate_from_low_confidence(self):
        base={'predicted_fof2_iri_mhz':8,'predicted_fof2_tec_mhz':8.1,
              'predicted_fof2_physics_mhz':8.1,'observed_fof2_mhz':8.2}
        records=[dict(base,fof2_quality='STANDARD'),dict(base,fof2_quality='EXTENDED')]
        a=paired_summary(records)
        self.assertEqual(a['paired_count'],1)
        self.assertEqual(a['extended_paired_count'],1)
        self.assertEqual(a['display_coverage_percent'],100)
        b=rollup(records)
        self.assertEqual(b['stages']['physics']['n'],1)
        self.assertEqual(b['extended_provisional_physics']['n'],1)

    def test_end_to_end_synthetic_prospective_sensitivity(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);(d/'animation').mkdir()
            now=datetime(2026,11,23,12,tzinfo=timezone.utc)
            times=[(now+timedelta(minutes=30*i)).isoformat().replace('+00:00','Z') for i in (1,2)]
            # 0.1 TECU scale, 2x2 geographical bilinear support across Japan
            v=round(self.partial*.2*10)
            (d/'animation'/'frames_0.json').write_text(json.dumps({'start':0,'values':[[v]*4,[v]*4]}))
            (d/'animation'/'index.json').write_text(json.dumps({'schema':'swift-ion-vtec-animation-v1',
                'metadata':{'is_forecast':True,'units':'TECU','time_step_minutes':30,'value_scale':10},
                'time_utc':times,'latitudes':[20,50],'longitudes':[120,155],
                'chunks':[{'file':'frames_0.json','count':2}]}))
            (d/'ionosphere.json').write_text(json.dumps({'metadata':{'is_forecast':False}}))
            def fake(t,lat,lon):return PROFILE_ALTITUDES,self.ne
            result=build(d/'animation',d/'ionosphere.json',d/'out.json',now=now,
                         iri_provider=fake,max_sites=4,japan_sites=4,
                         anchor_hours=.5,global_anchor_hours=.5)
            self.assertEqual(result['status'],'AVAILABLE')
            cells=result['frames'][0]['sites'];self.assertEqual(len(cells),4)
            self.assertTrue(all(c['fof2_quality']=='EXTENDED' for c in cells))
            self.assertTrue(all(c['fof2_tec_mhz'] is not None for c in cells))
            self.assertTrue(all(c['fof2_strict_mhz'] is None for c in cells))
            self.assertTrue(all(c['fof2_empirical_mhz'] is None and c['fof2_ai_mhz'] is None for c in cells))
            self.assertEqual(result['metadata']['fof2_quality_counts']['EXTENDED'],8)
            self.assertFalse(result['metadata']['fof2_extended_is_validated'])

if __name__=='__main__':unittest.main()
