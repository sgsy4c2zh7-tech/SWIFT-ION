import json
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_tec_skill import (build_snapshot, sample_station, score_observations,
                             store_snapshot, store_matches, recent_snapshots,
                             paired_summary, report, run, prune, iso, parse_utc)
from build_year_archive import read_daily

NOW=datetime(2026,11,22,12,0,tzinfo=timezone.utc)
SITE={'lat':35.68,'lon':139.76,'fof2_iri_mhz':8.5,'fof2_tec_mhz':7.6}

def obs(at,confidence=95):
    return {'stations':[{'station':'KOKUBUNJI','lat':35.68,'lon':139.76,
          'fof2_mhz':7.5,'hmf2_km':300,'observed_at':iso(at),
          'confidence':confidence,'confidence_known':True}]}

def model(now=NOW, tec=True):
    cells=[dict(SITE,fof2_tec_mhz=7.6 if tec else None)]
    frames=[]
    for h in (1,3,6,12,24):
        target=now+timedelta(hours=h)
        frames.append({'valid_at':iso(target),'sites':cells})
    return {'schema':'swift-ion-iri-tec-forecast-v1','status':'AVAILABLE',
         'metadata':{'issued_at':iso(now-timedelta(minutes=10))},'frames':frames}

class TestTecSkill(unittest.TestCase):
    def test_exact_sampling(self):
        s=sample_station(model()['frames'][0],35.68,139.76)
        self.assertAlmostEqual(s['predicted_fof2_tec_mhz'],7.6)
        self.assertAlmostEqual(s['predicted_fof2_iri_mhz'],8.5)

    def test_no_fake_farfield(self):
        self.assertIsNone(sample_station(model()['frames'][0],-45,11))

    def test_no_partial_tec_scale(self):
        s=sample_station(model(tec=False)['frames'][0],35.68,139.76)
        self.assertIsNone(s['predicted_fof2_tec_mhz'])

    def test_prospective_snapshot_contains_five_horizons(self):
        s,why=build_snapshot(model(),obs(NOW),NOW)
        self.assertEqual(why,'AVAILABLE')
        self.assertEqual(len(s['forecasts']),5)
        self.assertEqual(set(x['nominal_horizon_h'] for x in s['forecasts']),{1,3,6,12,24})
        self.assertTrue(all(parse_utc(f['valid_at'])>parse_utc(s['metadata']['issued_at']) for f in s['forecasts']))

    def test_model_staleness_rejected(self):
        x=model();x['metadata']['issued_at']=iso(NOW-timedelta(hours=8))
        s,reason=build_snapshot(x,obs(NOW),NOW)
        self.assertIsNone(s)
        self.assertEqual(reason,'MODEL_ISSUE_STALE_OR_FUTURE')

    def test_no_observation_preissue(self):
        s,_=build_snapshot(model(),obs(NOW),NOW)
        self.assertEqual(score_observations(obs(NOW),[s],NOW),[])

    def test_observation_matched_only_after_issue(self):
        s,_=build_snapshot(model(),obs(NOW),NOW)
        target=NOW+timedelta(hours=1)
        m=score_observations(obs(target),[s],target+timedelta(minutes=10))
        self.assertEqual(len(m),1)
        self.assertEqual(m[0]['predicted_fof2_tec_mhz'],7.6)
        self.assertEqual(m[0]['predicted_fof2_iri_mhz'],8.5)

    def test_low_confidence_not_counted(self):
        s,_=build_snapshot(model(),obs(NOW),NOW)
        self.assertEqual(score_observations(obs(NOW+timedelta(hours=1),confidence=60),[s],NOW+timedelta(hours=2)),[])

    def test_paired_identical_denominator(self):
        a={'predicted_fof2_iri_mhz':8.5,'predicted_fof2_tec_mhz':7.6,'observed_fof2_mhz':7.5}
        b={'predicted_fof2_iri_mhz':8.5,'predicted_fof2_tec_mhz':None,'observed_fof2_mhz':7.5}
        s=paired_summary([a,b])
        self.assertEqual(s['iri_all']['sample_count'],2)
        self.assertEqual(s['paired_iri']['sample_count'],1)
        self.assertEqual(s['paired_tec']['sample_count'],1)
        self.assertEqual(s['paired_count'],1)
        self.assertEqual(s['tec_coverage_percent'],50.0)

    def test_missing_pair_is_NA(self):
        a={'predicted_fof2_iri_mhz':8.5,'predicted_fof2_tec_mhz':None,'observed_fof2_mhz':7.5}
        s=paired_summary([a])
        self.assertIsNone(s['paired_tec']['hit_rate_percent'])
        self.assertIsNone(s['hit_rate_gain_pp'])

    def test_idempotent_archive(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            s,_=build_snapshot(model(),obs(NOW),NOW)
            store_snapshot(root,s);store_snapshot(root,s)
            self.assertEqual(len(recent_snapshots(root,NOW+timedelta(minutes=5))),1)
            target=NOW+timedelta(hours=1)
            rows=score_observations(obs(target),[s],target+timedelta(minutes=10))
            self.assertEqual(store_matches(root,rows,target+timedelta(minutes=10)),1)
            self.assertEqual(store_matches(root,rows,target+timedelta(minutes=10)),0)
            self.assertEqual(report(root,target+timedelta(minutes=10))['total_matches'],1)

    def test_end_to_end_archive_and_csv(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);docs=root/'docs';docs.mkdir()
            station_path=root/'observation.json';model_path=root/'model.json'
            station_path.write_text(json.dumps(obs(NOW)),encoding='utf8')
            model_path.write_text(json.dumps(model()),encoding='utf8')
            first=run(station_path,model_path,root/'history',docs,now=NOW,issue_new=True)
            self.assertTrue(first['archive']['new_snapshot_issued'])
            self.assertEqual(first['total_matches'],0)
            target=NOW+timedelta(hours=1)
            station_path.write_text(json.dumps(obs(target)),encoding='utf8')
            second=run(station_path,model_path,root/'history',docs,now=target+timedelta(minutes=10),issue_new=False)
            self.assertEqual(second['total_matches'],1)
            self.assertEqual(second['by_horizon']['1']['paired_count'],1)
            self.assertEqual(second['by_horizon']['1']['paired_tec']['hit_rate_percent'],100)
            self.assertTrue((docs/'tec_skill_daily.csv').exists())
            self.assertEqual(second['archive']['new_snapshot_issued'],False)

if __name__=='__main__':unittest.main()
