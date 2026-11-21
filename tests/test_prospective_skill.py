"""All tests offline and independent of external GitHub/IRI API calls."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_prospective_skill import (build_outlook, score_history, metrics, iso,
                                     next_utc_hour, run, fetch_previous_artifacts, SafeRedirect)

NOW = datetime(2026,11,21,12,0,tzinfo=timezone.utc)


class Array:
    def __init__(self, vals): self.values=vals

class FakeDensity(Array):
    ndim = 1
    dims = ('alt_km',)
    attrs = {'units':'m^-3'}
    def squeeze(self): return self

class FakeDataset(dict):
    def __init__(self):
        super().__init__(alt_km=Array([100,200,250,300,350,400,500,600,1000,2000]),
                         ne=FakeDensity([2e10,2e11,7e11,1.1e12,9e11,5e11,3e11,1e11,2e10,1e8]))

def fake_iri(dt,alt,lat,lon):
    assert dt.tzinfo is not None
    assert dt>NOW-timedelta(days=4)
    return FakeDataset()

def station(now=NOW, name='Station A',lat=35,lon=139, fof2=9.0,hmf2=300,cs=90):
    return {'station':name,'lat':lat,'lon':lon,'observed_at':iso(now),
            'confidence':cs,'confidence_known':True,
            'fof2_mhz':fof2,'hmf2_km':hmf2}

def snap(issued,station_name='Station A',lat=35,lon=139,valid=NOW,horizon=3,fof2=8.5,hmf2=325):
    return {'metadata':{'schema':'swift-ion-prospective-iri-baseline-v1','issued_at':iso(issued)},
            'forecasts':[{'station':station_name,'lat':lat,'lon':lon,
                          'valid_at':iso(valid),'nominal_horizon_h':horizon,
                          'actual_lead_h':3,'fof2_mhz':fof2,'hmf2_km':hmf2,
                          'peak_at_boundary':False}]}

class ProspectiveSkillTests(unittest.TestCase):
    def test_next_hour_and_no_expired_target(self):
        t=NOW.replace(minute=17)
        self.assertEqual(next_utc_hour(t).hour,13)
        self.assertEqual(next_utc_hour(NOW),NOW)
        outlook=build_outlook({'stations':[station()]},fake_iri,t,horizons=(1,3),published_at=t)
        self.assertEqual(len(outlook['forecasts']),2)
        self.assertGreater(next_utc_hour(t+timedelta(hours=1)),t)
        self.assertEqual(outlook['metadata']['is_tec_assimilated'],False)
        self.assertTrue(all(f['valid_at']>iso(t) for f in outlook['forecasts']))

    def test_prospective_good_match_metrics(self):
        report={'stations':[station()]}
        earlier=NOW-timedelta(hours=4)
        score=score_history(report,[snap(earlier)],NOW)
        self.assertEqual(score['matched_count'],1)
        self.assertEqual(score['horizons']['3']['fof2']['mae'],0.5)
        self.assertEqual(score['horizons']['3']['hmf2']['bias'],25)
        self.assertFalse(score['metadata']['is_swifttec_layer_forecast_skill'])

    def test_hindsight_issue_rejected(self):
        future=NOW+timedelta(minutes=1)
        score=score_history({'stations':[station()]},[snap(future)],NOW)
        self.assertEqual(score['matched_count'],0)
        self.assertIsNone(score['horizons']['3']['fof2']['rmse'])

    def test_timestamp_and_location_rejections(self):
        issued=NOW-timedelta(hours=4)
        obs={'stations':[station()]}
        wrongtime=snap(issued,valid=NOW+timedelta(hours=1))
        faraway=snap(issued,lat=-60,lon=-130)
        self.assertEqual(score_history(obs,[wrongtime,faraway],NOW)['matched_count'],0)

    def test_dedup_latest_issuance(self):
        report={'stations':[station()]}
        first=snap(NOW-timedelta(hours=5),fof2=3)
        second=snap(NOW-timedelta(hours=4),fof2=8.0)
        out=score_history(report,[first,second],NOW)
        self.assertEqual(out['matched_count'],1)
        self.assertEqual(out['horizons']['3']['fof2']['mae'],1.0)

    def test_missing_confidence_is_not_scored(self):
        s=station();s['confidence_known']=False
        result=score_history({'stations':[s]},[snap(NOW-timedelta(hours=3))],NOW)
        self.assertEqual(result['matched_count'],0)
        self.assertGreaterEqual(result['skipped']['confidence_unverified'],1)

    def test_hmf2_boundary_is_excluded_from_hmf2_only(self):
        f=snap(NOW-timedelta(hours=4));f['forecasts'][0]['peak_at_boundary']=True
        r=score_history({'stations':[station()]},[f],NOW)
        self.assertEqual(r['horizons']['3']['fof2']['count'],1)
        self.assertEqual(r['horizons']['3']['hmf2']['count'],0)

    def test_slow_generation_does_not_backdate_issued_forecast(self):
        start=NOW.replace(minute=17)
        completed=start+timedelta(hours=2)
        outlook=build_outlook({'stations':[station()]},fake_iri,start,
                              horizons=(1,3,6),published_at=completed)
        self.assertEqual(outlook['metadata']['issued_at'],iso(completed))
        self.assertTrue(all(f['actual_lead_h']>0 for f in outlook['forecasts']))
        self.assertTrue(all(f['valid_at']>iso(completed) for f in outlook['forecasts']))
        self.assertGreaterEqual(outlook['omitted_near_term_after_completion'],1)

    def test_no_history_is_pending_and_zero_not_claimed(self):
        r=score_history({'stations':[station()]},[],NOW)
        self.assertEqual(r['status'],'PENDING_HISTORY_OR_NO_EXACT_MATCHES')
        self.assertIsNone(r['horizons']['1']['fof2']['mae'])

    def test_build_from_fixture_no_web(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            obs=folder/'obs.json';obs.write_text(json.dumps({'stations':[station()]},default=str),encoding='utf-8')
            future,skill=run(obs,folder/'outlook.json',folder/'skill.json',now=NOW,
                iri_function=fake_iri,prior_snapshots=[],history_status='TEST_HISTORY_NONE',published_at=NOW)
            self.assertEqual(len(future['forecasts']),5)
            self.assertEqual(skill['matched_count'],0)
            self.assertTrue((folder/'outlook.json').exists())
            self.assertTrue((folder/'skill.json').exists())

    def test_read_only_artifact_zip_reader(self):
        payload=json.dumps(snap(NOW-timedelta(hours=4))).encode()
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as archive:
            archive.writestr('station_outlook.json',payload)
        index={'artifacts':[{'name':'swift-ion-prospective-123','id':123,
                             'created_at':iso(NOW),'expired':False}]}
        def fake_get(url,token,limit):
            self.assertEqual(token,'test-token')
            return json.dumps(index).encode() if 'per_page=100' in url else buf.getvalue()
        with patch('build_prospective_skill._get',side_effect=fake_get):
            data,state=fetch_previous_artifacts('owner/repo','test-token')
        self.assertEqual(state,'HISTORY_AVAILABLE')
        self.assertEqual(len(data),1)
        self.assertEqual(data[0]['forecasts'][0]['station'],'Station A')

    def test_no_token_has_explicit_error(self):
        data,state=fetch_previous_artifacts('owner/repo','')
        self.assertEqual(data,[])
        self.assertEqual(state,'GITHUB_ACTIONS_TOKEN_NOT_AVAILABLE')

    def test_redirect_strips_authorization_to_object_store(self):
        from urllib.request import Request
        req=Request('https://api.github.com/repos/a/b/actions/artifacts/1/zip',
                    headers={'Authorization':'Bearer hidden','Accept':'application/json'})
        new=SafeRedirect().redirect_request(req,None,302,'Moved',{},
              'https://objects.githubusercontent.com/path/signed.zip')
        self.assertFalse(any(k.lower()=='authorization' for k in new.headers))
        self.assertFalse(any(k.lower()=='authorization' for k in new.unredirected_hdrs))

    def test_statistics_are_model_minus_observation(self):
        x=metrics([(10,8),(5,9)],'MHz')
        self.assertEqual(x['mae'],3.0)
        self.assertEqual(x['bias'],-1.0)

if __name__=='__main__': unittest.main()
