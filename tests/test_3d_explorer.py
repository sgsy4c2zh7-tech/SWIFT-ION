import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'build_3d_explorer.py'
spec=importlib.util.spec_from_file_location('build_3d_explorer',MODULE)
b=importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
NOW=datetime(2026,11,21,12,tzinfo=timezone.utc)


def make_ion(path):
    alt=list(range(100,2001,25))
    ne=[8e11 * (2.718281828 ** (-((x-300)/100)**2)) for x in alt]
    cells=[{'lat':y,'lon':x,'vtec_swifttec_tecu':25.,'iri':{'hmf2_km':300,'nmf2_m3':8e11,'fof2_mhz':8.},
            'profile':{'alt_km':alt,'ne_m3':ne}} for y,x in [(35,139),(40,143),(0,0),(-20,60),(50,-100)]]
    path.write_text(json.dumps({'metadata':{'is_forecast':False},'frames':[{'valid_at':'2026-11-21T13:00:00Z','cells':cells}]}))


def make_isee(folder):
    folder.mkdir(parents=True)
    entries=[]
    for timestamp in ['2026-11-13T23:00:00Z','2026-11-13T23:05:00Z','2026-11-13T23:30:00Z']:
        name=timestamp.replace('-','').replace(':','').replace('T','_')+'.json'
        entry={'time_utc':timestamp,'file':name}
        frame={'time_utc':timestamp,'quantity':'VTEC','units':'TECU','source_product':'ISEE AGRID2',
               'lat_arr':[24.1+i for i in range(10)],'lon_arr':[122+j for j in range(10)],
               'grid':[[float(i+j+12) for j in range(10)] for i in range(10)]}
        (folder/name).write_text(json.dumps(frame))
        entries.append(entry)
    (folder/'index.json').write_text(json.dumps({'quantity':'VTEC','units':'TECU',
       'region':{'lat_min':24,'lat_max':46,'lon_min':122,'lon_max':150},
       'latest_source_hour_utc':'2026-11-13T23:00:00Z','frames':entries}))


def fake_provider(t,lat,lon):
    return list(range(100,2001,25)),[5e11 for _ in range(100,2001,25)],{'nmf2_m3':5e11,'hmf2_km':300,'fof2_mhz':6.35}


class ExplorerTests(unittest.TestCase):
    def test_site_profile_and_vtec(self):
        with tempfile.TemporaryDirectory() as td:
            ion=Path(td)/'ion.json';make_ion(ion)
            data=b.build_global(json.loads(ion.read_text()))
            self.assertEqual(len(data),1)
            self.assertEqual(len(data[0]['sites'][0]['ne_log10_m3']),len(b.ALTITUDES))
            self.assertEqual(data[0]['sites'][0]['vtec_swifttec_tecu'],25)

    def test_missing_isee_is_explicit_unavailable(self):
        with tempfile.TemporaryDirectory() as td:
            ion=Path(td)/'ion.json';make_ion(ion)
            result=b.build(ion,Path(td)/'missing',Path(td)/'out.json',now=NOW)
            self.assertEqual(result['japan']['status'],'UNAVAILABLE')
            self.assertEqual(len(result['global_frames']),1)
            self.assertFalse(result['metadata']['is_observed_3d_density'])

    def test_exact_time_iri_and_no_five_minute_fabrication(self):
        with tempfile.TemporaryDirectory() as td:
            ion=Path(td)/'ion.json';make_ion(ion)
            archive=Path(td)/'iseejapan';make_isee(archive)
            seen=[]
            def provider(t,lat,lon):
                seen.append(t)
                return fake_provider(t,lat,lon)
            result=b.build(ion,archive,Path(td)/'output.json',regional_sites=9,max_isee_frames=3,iri_provider=provider,now=NOW)
            self.assertEqual(result['japan']['status'],'AVAILABLE')
            self.assertEqual(len(result['japan']['frames']),2)  # 23:05 ignored
            self.assertEqual([f['valid_at'] for f in result['japan']['frames']],['2026-11-13T23:00:00Z','2026-11-13T23:30:00Z'])
            self.assertEqual(len(seen),18)
            self.assertEqual(set(b.iso(t) for t in seen),{'2026-11-13T23:00:00Z','2026-11-13T23:30:00Z'})
            self.assertGreater(result['japan']['observation_lag_hours'],1)
            self.assertEqual(result['japan']['frames'][0]['vtec']['grid_tecu'][0][0],12)

    def test_region_sample_has_multiple_cities(self):
        p=b.sample_lattice(36)
        self.assertIn((35.68,139.76),p)
        self.assertIn((43.06,141.35),p)
        self.assertIn((26.21,127.68),p)
        self.assertEqual(len(set(p)),36)

    def test_traversal_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);p.mkdir(exist_ok=True)
            (p/'index.json').write_text(json.dumps({'quantity':'VTEC','units':'TECU',
                'frames':[{'time_utc':'2026-11-13T23:30:00Z','file':'../other.json'}]}))
            index,entries=b.latest_halfhour_entries(p,3)
            self.assertEqual(entries,[])

    def test_reject_false_forecast_label(self):
        with tempfile.TemporaryDirectory() as td:
            ion=Path(td)/'ion.json';make_ion(ion)
            x=json.loads(ion.read_text());x['metadata']['is_forecast']=True
            with self.assertRaises(ValueError): b.build_global(x)

    def test_workflow_retains_original_history_steps(self):
        workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/pages.yml').read_text()
        for phrase in ['Record prospective IRI forecasts and score a rolling 365 days',
                       'Commit 365-day history to dedicated branch','Build GAIA-style IRI and ISEE Japan explorer',
                       'Calculate SWIFT-TEC VTEC forecast and 30-minute animation',
                       'Build science quality and retrospective reference report',
                       'Deploy GitHub Pages']:
            self.assertIn(phrase,workflow)

if __name__=='__main__':unittest.main()
