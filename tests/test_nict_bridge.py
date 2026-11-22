import sys, unittest, tempfile, json
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_nict_fof2 import (parse_normalized_csv, canonical, run,STATIONS,match_issued, download_official)
from build_prospective_skill import iso
from build_year_archive import write_daily,read_daily
from build_tec_skill import build_snapshot
from train_fof2_calibration import training_rows

class NICTBridgeTests(unittest.TestCase):
    def setUp(self):self.now=datetime(2026,11,23,12,0,tzinfo=timezone.utc)
    def test_jst_converts_without_assuming_utc(self):
        rows=parse_normalized_csv('station,time_jst,fof2_mhz,source\nKOKUBUNJI,2026-11-23 15:30:00,8.7,NICT_auto\n',now=self.now)
        self.assertEqual(rows[0]['observed_at'],'2026-11-23T06:30:00Z')
    def test_utc_requires_timezone(self):
        with self.assertRaisesRegex(ValueError,'No valid|errors|too few'):
            parse_normalized_csv('station,time_utc,fof2_mhz\nOKINAWA,2026-11-23T06:00:00,9.4\n',now=self.now)
    def test_unsupported_native_format_refused(self):
        with self.assertRaisesRegex(ValueError,'Unknown source format'):
            parse_normalized_csv('<html><body>4.5 foF2</body></html>',now=self.now)
    def test_unsupported_fake_endpoint_refused(self):
        with self.assertRaises(ValueError):download_official('https://example.com/observation.csv')
    def test_bad_numeric_and_future_rejected(self):
        with self.assertRaises(ValueError):
            parse_normalized_csv('station,time_utc,fof2_mhz\nWAKKANAI,2026-11-30T00:00:00Z,9.1\n',now=self.now)
        with self.assertRaises(ValueError):
            parse_normalized_csv('station,time_utc,fof2_mhz\nWAKKANAI,2026-11-23T06:00:00Z,-999\n',now=self.now)
    def test_fixed_stations_are_forecast_prior_to_any_observations(self):
        now=self.now
        frames=[]
        for h in [1,3,6,12,24,25]:
            frames.append({'valid_at':iso(now+timedelta(hours=h)),
                           'sites':[{'lat':lat,'lon':lon,'fof2_iri_mhz':8.0,'fof2_tec_mhz':8.5,
                            'fof2_physics_mhz':8.4,'fof2_empirical_mhz':None,'fof2_ai_mhz':None,
                            'fof2_quality':'STANDARD'} for lat,lon in STATIONS.values()]})
        model={'schema':'swift-ion-iri-tec-forecast-v1','metadata':{'issued_at':iso(now)},'status':'AVAILABLE','frames':frames}
        snapshot,reason=build_snapshot(model,{'stations':[]},now)
        self.assertEqual(reason,'AVAILABLE')
        self.assertEqual({x['station'] for x in snapshot['forecasts']},set(STATIONS))
    def test_archive_match_and_training_are_prospective(self):
        now=self.now
        t=now-timedelta(hours=3)
        issued=now-timedelta(hours=6)
        f={'station':'WAKKANAI','lat':45.16,'lon':141.75,'valid_at':iso(t),
           'nominal_horizon_h':3,'actual_lead_h':3,
           'predicted_fof2_iri_mhz':8.2,'predicted_fof2_tec_mhz':8.4,
           'predicted_fof2_physics_mhz':8.4,'predicted_fof2_empirical_mhz':None,
           'predicted_fof2_ai_mhz':None,'fof2_quality':'STANDARD','kp_forecast':3.4,'f107_available':120}
        snapshot={'metadata':{'schema':'swift-ion-tec-fof2-prospective-v1',
                 'issued_at':iso(issued),'source_issued_at':iso(issued)},'forecasts':[f]}
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);hist=root/'history';docs=root/'docs';imp=root/'nict_import';imp.mkdir()
            write_daily(hist/'tec_outlooks',issued.date(),[snapshot])
            (imp/'WAKKANAI.csv').write_text('station,time_jst,fof2_mhz,source\nWAKKANAI,'+(t+timedelta(hours=9)).strftime('%Y-%m-%d %H:%M:%S')+',8.6,NICT_auto\n')
            d=run(hist,docs,imp,now=now)
            self.assertEqual(d['observations_retained'],1)
            self.assertEqual(d['prospective_matches_retained'],1)
            self.assertEqual(d['stations']['WAKKANAI']['hit_rate_pct'],100)
            self.assertEqual(training_rows(hist,now)[0]['data_provider'],'NICT')
            # Idempotent rerun
            d=run(hist,docs,imp,now=now)
            self.assertEqual(d['new_observations'],0)
            self.assertEqual(d['new_prospective_matches'],0)
            self.assertEqual(len(read_daily(hist/'nict_matches',t.date())),1)
    def test_cannot_match_post_observation_snapshot(self):
        obs={'station':'KOKUBUNJI','lat':35.71,'lon':139.49,'observed_at':iso(self.now-timedelta(hours=2)),
             'fof2_mhz':9,'source':'NICT_auto','quality':'AUTO_UNVERIFIED'}
        later=self.now-timedelta(hours=1)
        snap={'metadata':{'issued_at':iso(later),'source_issued_at':iso(later)},
              'forecasts':[{'station':'KOKUBUNJI','lat':35.71,'lon':139.49,
                  'valid_at':obs['observed_at'],'nominal_horizon_h':1,'predicted_fof2_physics_mhz':9.5}]}
        self.assertEqual(match_issued([obs],[snap],self.now),[])

if __name__=='__main__':unittest.main()
