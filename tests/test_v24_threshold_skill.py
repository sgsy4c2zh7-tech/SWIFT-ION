"""Synthetic unit tests for the revised ±2 MHz headline.

These samples are deliberately artificial; no artificial measurement is
fed into production or presented as an observed skill rate.
"""
import csv, tempfile, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_tec_skill import metric, paired_summary, kp_activity, export_csv
from build_fof2_stage_skill import score, rollup, write_csv
from build_nict_fof2 import summarize


def record(err, *, kp=3.2, confirmed=True, quality='STANDARD', station='KOKUBUNJI'):
    return {'station':station,'observed_fof2_mhz':8.,
            'predicted_fof2_iri_mhz':8.5,
            'predicted_fof2_tec_mhz':8.+err,
            'predicted_fof2_physics_mhz':8.+err,
            'predicted_fof2_empirical_mhz':8.+err,
            'predicted_fof2_ai_mhz':8.+err,
            'kp_forecast':kp,'kp_3day_confirmed':confirmed,
            'fof2_quality':quality}

class TestV24Thresholds(unittest.TestCase):
    def test_three_thresholds_distinguish_borderline_errors(self):
        rows=[record(e) for e in (-3.01,-3,-2.01,-2,-1.01,-1,0,1,1.01,2,2.01,3,3.01)]
        s=metric(rows,'predicted_fof2_tec_mhz')
        self.assertEqual(s['sample_count'],13)
        self.assertEqual(s['hits_by_threshold_mhz'],{'1':3,'2':7,'3':11})
        self.assertEqual(s['hit_count'],7)
        self.assertEqual(s['hit_rate_percent'],round(700/13,2))
        self.assertGreater(s['rmse'],s['mae'])
        self.assertTrue(s['mape_pct']>0)

    def test_missing_rows_not_zero_percent(self):
        r=metric([dict(record(2.5),predicted_fof2_tec_mhz=None)],'predicted_fof2_tec_mhz')
        self.assertEqual(r['sample_count'],0)
        self.assertIsNone(r['hit_rate_percent'])
        self.assertIsNone(r['hit_rate_by_threshold_pct']['3'])

    def test_kp_activity_uses_forecast_kp_not_measured_storm(self):
        for x,y in [(0,'QUIET_KP_LT_4'),(3.99,'QUIET_KP_LT_4'),
                    (4,'ACTIVE_KP_4_TO_5'),(4.99,'ACTIVE_KP_4_TO_5'),
                    (5,'STORM_KP_GE_5'),(9,'STORM_KP_GE_5'),
                    (None,'UNKNOWN'),(10,'UNKNOWN')]:
            self.assertEqual(kp_activity(x),y)

    def test_main_excludes_unconfirmed_and_extended_but_keeps_cohorts(self):
        rows=[record(1.5,kp=2.7),record(2.3,kp=5.5),
              record(0.0,kp=4.5),record(0.0,confirmed=False),record(0.0,quality='EXTENDED')]
        s=paired_summary(rows)
        self.assertEqual(s['kp3day_paired_count'],3)
        self.assertEqual(s['kp3day_tec']['hit_count'],2)
        self.assertEqual(s['kp3day_tec']['hits_by_threshold_mhz'],{'1':1,'2':2,'3':3})
        self.assertEqual(s['kp3day_by_activity']['QUIET_KP_LT_4']['paired_count'],1)
        self.assertEqual(s['kp3day_by_activity']['ACTIVE_KP_4_TO_5']['paired_count'],1)
        self.assertEqual(s['kp3day_by_activity']['STORM_KP_GE_5']['paired_count'],1)
        self.assertEqual(s['extended_paired_count'],1)
        self.assertEqual(s['kp3day_iri']['sample_count'],3)

    def test_stage_scores_match_main_threshold(self):
        data=[record(1.4),record(2.7)]
        s=score(data,'physics')
        self.assertEqual(s['hits'],1)
        self.assertEqual(s['hit_pct'],50.0)
        self.assertEqual(s['hits_by_threshold_mhz'],{'1':0,'2':1,'3':2})
        r=rollup(data)
        self.assertEqual(r['kp3day_confirmed']['stages']['physics']['hit_pct'],50)
        self.assertEqual(r['empirical_ai_same_observations']['gain_hit_pp'],0)

    def test_nict_scores_add_all_thresholds(self):
        r=summarize([record(1.4),record(2.7),record(3.5,quality='EXTENDED')])
        x=r['KOKUBUNJI']['stages']['physics']
        self.assertEqual(x['n'],2)
        self.assertEqual(x['hit_rate_pct'],50)
        self.assertEqual(x['hit_rate_by_threshold_pct'],{'1':0.0,'2':50.0,'3':100.0})
        self.assertIsNotNone(x['rmse_mhz'])
        self.assertIsNone(r['WAKKANAI']['stages']['physics']['hit_rate_pct'])

    def test_csv_reports_include_thresholds(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            s=paired_summary([record(1.5)])
            export_csv(folder/'tec.csv',[{'day_utc':'2026-11-23','horizon_h':24,'summary':s}], 'day_utc')
            with (folder/'tec.csv').open(encoding='utf-8-sig') as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row['same_issue_kp3day_hit_pct_1mhz'],'0.0')
            self.assertEqual(row['same_issue_kp3day_hit_pct_2mhz'],'100.0')
            self.assertEqual(row['same_issue_kp3day_hit_pct_3mhz'],'100.0')
            z=rollup([record(1.5)])
            write_csv(folder/'stage.csv',[{'day_utc':'2026-11-23','horizon_h':24,'summary':z}],'day_utc')
            with (folder/'stage.csv').open(encoding='utf-8-sig') as f:
                row=next(csv.DictReader(f))
            self.assertEqual(row['hit_pct_1mhz'],'0.0')
            self.assertEqual(row['hit_pct_2mhz'],'100.0')
            self.assertEqual(row['hit_pct_3mhz'],'100.0')

if __name__=='__main__':unittest.main()
