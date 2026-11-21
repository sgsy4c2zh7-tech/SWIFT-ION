import gzip
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_quality_report import (stats,archive_cells,model_discrepancy,quality_summary,retrospective,build)

class QualityTests(unittest.TestCase):
    def test_stats(self):
        s=stats([10,20,30],[11,18,27])
        self.assertEqual(s['sample_count'],3)
        self.assertEqual(s['mae_tecu'],2)
        self.assertEqual(s['bias_tecu'],1.333)

    def fixture(self,base, now, valid, issued):
        frames=[{'valid_at':valid.isoformat(),'cells':[
            {'lat':i,'lon':0,'vtec_tecu':12} for i in range(31)]}]
        forecast={'metadata':{'is_forecast':True,'generated_at':issued.isoformat()},'frames':frames}
        archive=base/'archive';archive.mkdir(exist_ok=True)
        data={'time_utc':valid.isoformat(),'lat_arr':list(range(31)),'lon_arr':[0], 'grid':[[10] for _ in range(31)]}
        path=archive/'one.json.gz'
        with gzip.open(path,'wt',encoding='utf-8') as f:json.dump(data,f)
        idx={'updated_utc':now.isoformat(),'frames':[{'time_utc':valid.isoformat(),'file':'one.json.gz'}]}
        (archive/'index.json').write_text(json.dumps(idx),encoding='utf-8')
        return forecast,archive

    def test_prospective_archive_evaluation(self):
        with tempfile.TemporaryDirectory() as d:
            now=datetime(2026,11,22,tzinfo=timezone.utc)
            valid=now-timedelta(hours=1)
            forecast,archive=self.fixture(Path(d),now,valid,valid-timedelta(hours=24))
            result=retrospective(forecast,archive,now)
            self.assertEqual(result['evaluated_frames'],1)
            self.assertEqual(result['frames'][0]['mae_tecu'],2)

    def test_hindcast_not_scored(self):
        with tempfile.TemporaryDirectory() as d:
            now=datetime(2026,11,22,tzinfo=timezone.utc);valid=now-timedelta(hours=2)
            forecast,archive=self.fixture(Path(d),now,valid,now)
            result=retrospective(forecast,archive,now)
            self.assertEqual(result['frames'][0]['status'],'ineligible')

    def test_future_not_scored(self):
        with tempfile.TemporaryDirectory() as d:
            now=datetime(2026,11,22,tzinfo=timezone.utc);valid=now+timedelta(hours=1)
            forecast,archive=self.fixture(Path(d),now,valid,now-timedelta(hours=1))
            result=retrospective(forecast,archive,now)
            self.assertEqual(result['frames'][0]['status'],'pending')

    def test_quality_discrepancy_not_accuracy(self):
        frame={'cells':[{'vtec_swifttec_tecu':20,'iri_partial_tec_100_2000_tecu':15,'tec_scenario':None}],
               'map_cells':[{'nearest_iri_km':1000,'method':'IRI_RUN'},{'nearest_iri_km':2000,'method':'SPATIAL_INTERPOLATION'}]}
        self.assertEqual(model_discrepancy(frame)['median_signed_difference_tecu'],5)
        self.assertEqual(quality_summary(frame)['interpolated_more_than_1500km'],1)

    def test_full_pipeline_without_archive(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);now=datetime(2026,11,22,tzinfo=timezone.utc)
            f={'valid_at':now.isoformat(),'cells':[{'vtec_swifttec_tecu':15,'iri_partial_tec_100_2000_tecu':10,'tec_scenario':None,'iri':{'peak_at_boundary':False}}], 'map_cells':[{'lat':0,'lon':0,'method':'IRI_RUN','nearest_iri_km':0}]}
            ion={'metadata':{'is_forecast':False,'iri_model':'iri2020'},'frames':[f]}
            tec={'metadata':{'is_forecast':True,'generated_at':now.isoformat()},'frames':[]}
            (root/'ion.json').write_text(json.dumps(ion));(root/'tec.json').write_text(json.dumps(tec))
            out=build(root/'ion.json',root/'tec.json',root/'missing',root/'quality.json',now)
            self.assertEqual(out['retrospective_noaa_glotec']['status'],'unavailable')
            self.assertTrue((root/'quality.json').exists())

if __name__=='__main__':unittest.main()
