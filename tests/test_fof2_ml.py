"""Deterministic synthetic tests only. No synthetic observation enters production."""
import sys, unittest, tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fof2_ml import feature_vector,stage_predict,SCHEMA,EMP_NAMES,AI_NAMES,solve_ridge
from build_fof2_drivers import parse_kp,parse_f107,drivers_at
from build_fof2_stage_skill import rollup,run
from build_year_archive import write_daily
from train_fof2_calibration import fit,training_rows

NOW=datetime(2026,11,22,12,tzinfo=timezone.utc)

def stamp(dt):return dt.isoformat().replace('+00:00','Z')

class TestThreeStageFoF2(unittest.TestCase):
    def test_model_missing_stays_physical(self):
        p=stage_predict(8,7.5,35,139,stamp(NOW+timedelta(hours=2)),None,None,None)
        self.assertEqual(p['stage'],'PHYSICS')
        self.assertEqual(p['selected'],8)
        self.assertIsNone(p['empirical']);self.assertIsNone(p['ai'])

    def test_physical_missing_no_artificial_iri_fallback(self):
        r=stage_predict(None,7.5,35,139,stamp(NOW+timedelta(hours=2)),None,None,None)
        self.assertIsNone(r['selected'])
        self.assertEqual(r['stage'],'UNAVAILABLE')

    def test_empirical_and_ai_activate_only_with_valid_model(self):
        model={'schema':SCHEMA,'trained_at':stamp(NOW),
               'empirical':{'active':True,'coefficients':[.2]+[0]*(len(EMP_NAMES)-1)},
               'ai':{'active':True,'coefficients':[.1]+[0]*(len(AI_NAMES)-1)}}
        r=stage_predict(8,7.5,35,139,stamp(NOW+timedelta(hours=2)),4,140,model)
        self.assertEqual(r['stage'],'AI')
        self.assertAlmostEqual(r['physics'],8)
        self.assertAlmostEqual(r['empirical'],8.2)
        self.assertAlmostEqual(r['ai'],8.3)
        self.assertAlmostEqual(r['selected'],8.3)

    def test_never_use_model_trained_after_target(self):
        model={'schema':SCHEMA,'trained_at':stamp(NOW+timedelta(days=1)),
               'empirical':{'active':True,'coefficients':[.5]+[0]*(len(EMP_NAMES)-1)},
               'ai':{'active':False,'coefficients':None}}
        r=stage_predict(7,7,35,139,stamp(NOW+timedelta(hours=1)),4,130,model)
        self.assertEqual(r['stage'],'PHYSICS')

    def test_features_finite_without_optional_drivers(self):
        self.assertEqual(len(feature_vector(7,6,35,139,stamp(NOW),None,None)),len(EMP_NAMES))
        self.assertEqual(len(feature_vector(7,6,35,139,stamp(NOW),None,None,'ai')),len(AI_NAMES))

    def test_ridge_solver_regularized(self):
        x=[[1.,0],[1.,1],[1.,2]];y=[1,2,3]
        beta=solve_ridge(x,y,reg=.0001)
        self.assertAlmostEqual(beta[0],1,places=2)
        self.assertAlmostEqual(beta[1],1,places=2)

    def test_driver_forecast_vs_observation(self):
        obj=[{'time_tag':'2026-11-22T12:00:00','kp':4.5,'observed':'predicted'},
             {'time_tag':'2026-11-22T15:00:00','kp':7,'observed':'observed'}]
        pred=parse_kp(obj,NOW)
        self.assertEqual(len(pred),1)
        self.assertEqual(pred[0]['kp'],4.5)
        src={'schema':'swift-ion-fof2-driver-v1','kp_predicted':pred,
             'f107_recent_observed':{'value_sfu':155,'observed_at_utc':stamp(NOW-timedelta(hours=2))}}
        kp,f107=drivers_at(src,stamp(NOW+timedelta(hours=1)),NOW)
        self.assertEqual(kp,4.5);self.assertEqual(f107,155)
        self.assertEqual(drivers_at(src,stamp(NOW+timedelta(days=4)),NOW)[0],None)

    def test_missing_observation_prevents_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            x=fit(tmp,NOW)
            self.assertFalse(x['empirical']['active'])
            self.assertFalse(x['ai']['active'])
            self.assertEqual(x['status'],'PHYSICS_ONLY')

    def test_exclude_future_labels_from_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            day=(NOW-timedelta(days=1)).date()
            valid=NOW-timedelta(hours=12)
            common={'station':'ST','lat':35.,'lon':140.,'valid_at':stamp(valid),
                    'issued_at':stamp(valid-timedelta(hours=3)),
                    'predicted_fof2_iri_mhz':8,'predicted_fof2_physics_mhz':8.3,
                    'observed_fof2_mhz':8.1}
            past={**common,'observed_at':stamp(NOW-timedelta(hours=2))}
            future={**common,'observed_at':stamp(NOW+timedelta(hours=2))}
            too_recent={**common,'observed_at':stamp(NOW-timedelta(minutes=20))}
            write_daily(Path(tmp)/'tec_matches',day,[past,future,too_recent])
            rows=training_rows(tmp,NOW)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['actual'],8.1)

    def test_pair_same_denominator(self):
        a={'observed_fof2_mhz':8.0,'predicted_fof2_physics_mhz':9.5,
           'predicted_fof2_empirical_mhz':8.8,'predicted_fof2_ai_mhz':8.5}
        b={'observed_fof2_mhz':8.0,'predicted_fof2_physics_mhz':8.5,
           'predicted_fof2_empirical_mhz':None,'predicted_fof2_ai_mhz':None}
        result=rollup([a,b])
        self.assertEqual(result['stages']['physics']['n'],2)
        self.assertEqual(result['stages']['empirical']['n'],1)
        self.assertEqual(result['stages']['ai']['n'],1)
        self.assertEqual(result['empirical_ai_same_observations']['n'],1)
        self.assertEqual(result['empirical_ai_same_observations']['gain_hit_pp'],0)
        self.assertGreater(result['empirical_ai_same_observations']['mae_gain_mhz'],0)

    def test_daily_archive_report_no_hindcast(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=(NOW-timedelta(days=1)).date();valid=NOW-timedelta(hours=8)
            row={'station':'ST','lat':35.,'lon':140.,'valid_at':stamp(valid),
                    'issued_at':stamp(valid-timedelta(hours=3)),
                    'observed_at':stamp(NOW-timedelta(hours=7)),
                    'nominal_horizon_h':3,'predicted_fof2_physics_mhz':8.5,
                    'predicted_fof2_empirical_mhz':8.1,
                    'predicted_fof2_ai_mhz':8.05,'observed_fof2_mhz':8.0}
            write_daily(Path(tmp)/'tec_matches',d,[row])
            out=run(tmp,Path(tmp)/'docs',now=NOW)
            self.assertEqual(out['total_matches'],1)
            self.assertEqual(out['by_horizon']['3']['stages']['physics']['n'],1)
            self.assertEqual(out['by_horizon']['1']['stages']['physics']['n'],0)
            self.assertTrue((Path(tmp)/'docs/fof2_stage_daily.csv').is_file())

if __name__=='__main__':unittest.main()
