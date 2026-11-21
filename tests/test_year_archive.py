import sys
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_year_archive import (write_daily,read_daily,update_matches,update_observations,
    recent_outlooks,store_outlook,report_year,prune,metric_summary,run)
from build_prospective_skill import iso

NOW=datetime(2026,11,21,12,0,tzinfo=timezone.utc)


def match(when=NOW,h=3,issue=None,fof2pred=6.5,fof2obs=7.0,hmf2pred=300,hmf2obs=315):
    return {'station':'S','lat':20.,'lon':130.,'observed_at':iso(when),
      'issued_at':iso(issue or when-timedelta(hours=4)),'valid_at':iso(when),
      'nominal_horizon_h':h,'actual_lead_h':4,
      'observed_fof2_mhz':fof2obs,'predicted_fof2_mhz':fof2pred,
      'observed_hmf2_km':hmf2obs,'predicted_hmf2_km':hmf2pred,
      'time_gap_minutes':0.,'confidence':95,'hmf2_peak_at_boundary':False}


def outlook(issued=NOW-timedelta(hours=2)):
    return {'metadata':{'schema':'swift-ion-prospective-iri-baseline-v1','issued_at':iso(issued)},'forecasts':[]}

class TestYearArchive(unittest.TestCase):
    def test_daily_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            items=[{'station':'S','float':1.5},{'unicode':'高'}]
            write_daily(root,NOW.date(),items)
            self.assertEqual(read_daily(root,NOW.date()),items)

    def test_forecast_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store_outlook(root,outlook());store_outlook(root,outlook())
            self.assertEqual(len(read_daily(root/'outlooks',(NOW-timedelta(hours=2)).date())),1)

    def test_filter_future_issue(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store_outlook(root,outlook(NOW-timedelta(hours=2)))
            store_outlook(root,outlook(NOW+timedelta(hours=1)))
            self.assertEqual(len(recent_outlooks(root,NOW)),1)

    def test_observation_no_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            obs={'stations':[{'station':'S','lat':35.,'lon':140.,'observed_at':iso(NOW),
                               'fof2_mhz':8.,'hmf2_km':320.,'confidence':90,'confidence_known':True}]}
            self.assertEqual(update_observations(root,obs,NOW),1)
            self.assertEqual(update_observations(root,obs,NOW),0)
            self.assertEqual(len(read_daily(root/'observations',NOW.date())),1)

    def test_hit_rate_and_error(self):
        a=match();b=match(when=NOW-timedelta(hours=1),fof2pred=8.5,fof2obs=7.,hmf2pred=400,hmf2obs=315)
        r=metric_summary([a,b],'fof2')
        self.assertEqual(r['sample_count'],2)
        self.assertEqual(r['hit_count'],1)
        self.assertEqual(r['hit_rate_percent'],50.)
        self.assertEqual(r['mae'],1.0)
        self.assertEqual(metric_summary([a,b],'hmf2')['hit_count'],1)

    def test_missing_is_not_zero_percent(self):
        r=metric_summary([match(fof2pred=None,fof2obs=None)],'fof2')
        self.assertIsNone(r['hit_rate_percent'])
        self.assertEqual(r['sample_count'],0)

    def test_no_late_issue_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=match(issue=NOW-timedelta(minutes=15))
            self.assertEqual(update_matches(root,[p],NOW),0)
            self.assertEqual(read_daily(root/'matches',NOW.date()),[])

    def test_latest_issue_wins_and_no_double_count(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            early=match(issue=NOW-timedelta(hours=5),fof2pred=3)
            later=match(issue=NOW-timedelta(hours=2),fof2pred=7)
            self.assertEqual(update_matches(root,[early],NOW),1)
            self.assertEqual(update_matches(root,[later],NOW),0)
            self.assertEqual(update_matches(root,[early],NOW),0)
            arr=read_daily(root/'matches',NOW.date())
            self.assertEqual(len(arr),1)
            self.assertEqual(arr[0]['predicted_fof2_mhz'],7)

    def test_same_target_not_counted_multiple_times(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            first=match();first['observed_at']=iso(NOW-timedelta(minutes=20));first['time_gap_minutes']=-20
            nearer=match();nearer['observed_at']=iso(NOW-timedelta(minutes=2));nearer['time_gap_minutes']=-2
            self.assertEqual(update_matches(root,[first],NOW),1)
            self.assertEqual(update_matches(root,[nearer],NOW),0)
            self.assertEqual(report_year(root,NOW)['total_matches'],1)
            self.assertEqual(read_daily(root/'matches',NOW.date())[0]['observed_at'],nearer['observed_at'])

    def test_365day_prune(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            old=NOW.date()-timedelta(days=365)
            keep=NOW.date()-timedelta(days=364)
            write_daily(root/'matches',old,[match()])
            write_daily(root/'matches',keep,[match()])
            self.assertEqual(prune(root,NOW.date()),1)
            self.assertEqual(read_daily(root/'matches',old),[])
            self.assertEqual(len(read_daily(root/'matches',keep)),1)

    def test_annual_report_no_fabricated_year_of_data(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            report=report_year(root,NOW)
            self.assertEqual(report['total_matches'],0)
            self.assertEqual(len(report['daily']),365*5)
            self.assertIsNone(report['by_horizon']['1']['fof2']['hit_rate_percent'])
            self.assertEqual(report['status'],'AWAITING_PROSPECTIVE_MATCHES')

    def test_report_persists_known_result(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);update_matches(root,[match()],NOW)
            rep=report_year(root,NOW)
            self.assertEqual(rep['total_matches'],1)
            self.assertEqual(rep['by_horizon']['3']['fof2']['hit_rate_percent'],100.)

    def test_schedule_outside_6_hour_no_new_issue(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); docs=root/'docs';docs.mkdir()
            obs={'metadata':{'generated_at':iso(NOW)},'stations':[]}
            (docs/'ionosonde_validation.json').write_text(json.dumps(obs))
            old=outlook(NOW-timedelta(hours=2))
            store_outlook(root/'archive',old)
            res,_,year=run(docs/'ionosonde_validation.json',root/'archive',docs,now=NOW,issue_new=False)
            self.assertEqual(res['metadata']['issued_at'],old['metadata']['issued_at'])
            self.assertFalse(year['archive']['new_outlook_issued'])
            self.assertEqual(len(recent_outlooks(root/'archive',NOW)),1)

    def test_previous_issue_scored_before_current_issue(self):
        # End-to-end integration without requiring compiled IRI.
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);docs=root/'docs';docs.mkdir()
            obs={'metadata':{'generated_at':iso(NOW)},'stations':[{
                'station':'S','lat':20,'lon':130,'observed_at':iso(NOW-timedelta(minutes=2)),
                'confidence':99,'confidence_known':True,'fof2_mhz':7.,'hmf2_km':310.}]}
            (docs/'ionosonde_validation.json').write_text(json.dumps(obs))
            old=outlook(NOW-timedelta(hours=4))
            old['forecasts']=[{'station':'S','lat':20.,'lon':130.,'valid_at':iso(NOW),
                         'nominal_horizon_h':3,'actual_lead_h':4,
                         'fof2_mhz':7.1,'hmf2_km':312.,'peak_at_boundary':False}]
            store_outlook(root/'archive',old)
            class Density:
                dims=('alt_km',)
                ndim=1
                attrs={'units':'m^-3'}
                def __init__(self, values): self.values=values
                def squeeze(self): return self
            class Altitudes:
                def __init__(self, values): self.values=values
            def fake_iri(t, alt, lat, lon):
                al=list(range(100,2001,25))
                ne=[1e11]*len(al)
                ne[al.index(300)]=4e11
                return {'ne':Density(ne),'alt_km':Altitudes(al)}
            new, skill, year=run(docs/'ionosonde_validation.json',root/'archive',docs,now=NOW,iri_function=fake_iri,published_at=NOW)
            self.assertEqual(skill['matched_count'],1)
            self.assertEqual(year['total_matches'],1)
            self.assertTrue((docs/'year_daily.csv').exists())
            self.assertTrue((docs/'year_accuracy.json').exists())
            self.assertTrue(new['forecasts'])

if __name__=='__main__': unittest.main()
