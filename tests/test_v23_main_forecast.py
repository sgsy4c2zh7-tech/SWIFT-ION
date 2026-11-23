"""Synthetic tests for same-run Kp provenance and 72h prospective foF2."""
import json, sys, tempfile, unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_fof2_drivers import same_issue_swifttec_kp,build,drivers_at
from build_tec_skill import (HORIZONS_H,build_snapshot,score_observations,store_snapshot,
                              recent_snapshots,paired_summary,report,store_matches)
from build_fof2_stage_skill import rollup
from build_year_archive import write_daily
from train_fof2_calibration import fit

NOW=datetime(2026,11,23,6,tzinfo=timezone.utc)
def iso(x):return x.isoformat().replace('+00:00','Z')

def dummy_kp():
    start=NOW.replace(hour=0)
    slots=[{'valid_from_utc':iso(start+timedelta(hours=3*i)),'kp':3+i/10} for i in range(24)]
    return {'schema':'swift-ion-swifttec-issue-kp3day-v1','source_mode':'SWIFTTEC_SAME_ISSUE_NOAA_3DAY',
      'generated_at':iso(NOW-timedelta(minutes=10)),'valid_from_utc':iso(start),
      'valid_until_exclusive_utc':iso(start+timedelta(days=3)),'slots':slots}

def mock_model():
    site={'lat':35.71,'lon':139.49,'fof2_iri_mhz':8.1,'fof2_tec_mhz':8.0,
          'fof2_physics_mhz':7.8,'fof2_empirical_mhz':8.0,
          'fof2_ai_mhz':None,'fof2_quality':'STANDARD','kp_3day_confirmed':True,'kp_forecast':4.0}
    frames=[{'valid_at':iso(NOW+timedelta(hours=h)),'sites':[site]} for h in HORIZONS_H]
    return {'schema':'swift-ion-iri-tec-forecast-v1','status':'AVAILABLE',
      'metadata':{'issued_at':iso(NOW-timedelta(minutes=10))},'frames':frames}

class TestPrimarySkillV23(unittest.TestCase):
    def test_provenance_exact_24_kp_bins(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'kp.json';path.write_text(json.dumps(dummy_kp()))
            rows=same_issue_swifttec_kp(path,NOW)
            self.assertEqual(len(rows),24)
            self.assertEqual(rows[0]['kp'],3)
            self.assertEqual(rows[-1]['kp'],5.3)
    def test_damaged_kp_not_confirmed(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'kp.json'
            d=dummy_kp();d['slots'][3]['kp']=9.5;path.write_text(json.dumps(d))
            self.assertIsNone(same_issue_swifttec_kp(path,NOW))
    def test_kp_outside_original_three_days_is_absent(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'kp.json';path.write_text(json.dumps(dummy_kp()))
            obj=build(NOW,fetch=lambda url:[],swiftec_kp=path)
            self.assertEqual(obj['kp_source_mode'],'SWIFTTEC_SAME_ISSUE_NOAA_3DAY')
            self.assertEqual(drivers_at(obj,iso(NOW+timedelta(hours=1)),NOW)[0],3.2)
            self.assertIsNone(drivers_at(obj,iso(NOW+timedelta(hours=75)),NOW)[0])
    def test_snapshot_includes_72h(self):
        s,why=build_snapshot(mock_model(),{'stations':[]},NOW)
        self.assertEqual(why,'AVAILABLE')
        self.assertIn(72,{x['nominal_horizon_h'] for x in s['forecasts']})
        self.assertTrue(any(x['kp_3day_confirmed'] for x in s['forecasts']))
    def test_72h_observation_matches_prior_issued_forecast(self):
        s,_=build_snapshot(mock_model(),{'stations':[]},NOW)
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);store_snapshot(root,s)
            later=NOW+timedelta(hours=72,minutes=10)
            old=recent_snapshots(root,later)
            self.assertEqual(len(old),1)
            obs={'stations':[{'station':'KOKUBUNJI','lat':35.71,'lon':139.49,
               'fof2_mhz':8.,'observed_at':iso(NOW+timedelta(hours=72)),
               'confidence':95,'confidence_known':True}]}
            rows=score_observations(obs,old,later)
            self.assertTrue(any(x['nominal_horizon_h']==72 for x in rows))
            store_matches(root,rows,later)
            self.assertEqual(report(root,later)['by_horizon']['72']['kp3day_paired_count'],1)
    def test_primary_score_excludes_unverified_legacy_and_extended(self):
        base={'predicted_fof2_iri_mhz':8.5,'predicted_fof2_tec_mhz':8.1,
              'observed_fof2_mhz':8.0,'fof2_quality':'STANDARD'}
        data=[dict(base,kp_3day_confirmed=True),dict(base,kp_3day_confirmed=False),
              dict(base,fof2_quality='EXTENDED',kp_3day_confirmed=True)]
        x=paired_summary(data)
        self.assertEqual(x['paired_count'],2)
        self.assertEqual(x['kp3day_paired_count'],1)
        self.assertEqual(x['kp3day_tec']['hit_rate_percent'],100)
        self.assertEqual(x['extended_paired_count'],1)
    def test_stage_report_keeps_confirmed_subset_separate(self):
        base={'fof2_quality':'STANDARD','observed_fof2_mhz':8.0,'predicted_fof2_physics_mhz':8.1,
              'predicted_fof2_empirical_mhz':8.03,'predicted_fof2_ai_mhz':8.01}
        x=rollup([dict(base,kp_3day_confirmed=True),dict(base,kp_3day_confirmed=False)])
        self.assertEqual(x['stages']['physics']['n'],2)
        self.assertEqual(x['kp3day_confirmed']['stages']['physics']['n'],1)
    def test_initial_ml_state_is_not_fabricated(self):
        with tempfile.TemporaryDirectory() as root:
            d=fit(root,NOW)
            self.assertEqual(d['status'],'PHYSICS_ONLY')
            self.assertIsNone(d['empirical']['coefficients'])
            self.assertIsNone(d['ai']['coefficients'])
            self.assertEqual(d['forecast_target'][:9],'SWIFT-TEC')

if __name__=='__main__':unittest.main()
