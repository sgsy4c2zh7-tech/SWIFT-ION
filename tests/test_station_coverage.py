"""No-network tests: sample only actual input stations and keep patch idempotent."""
from __future__ import annotations
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from station_coverage import (
    TARGET_STATIONS, balanced_global_sample, geographic_bin, coverage_summary,
    LATITUDE_BANDS, LONGITUDE_BANDS,
)
from apply_station_coverage_patch import apply


def station(name, lat, lon, confidence_known=True):
    return {'station':name,'lat':lat,'lon':lon,'confidence_known':confidence_known,
            'fof2_mhz':7.3,'hmf2_km':300.0}


class StationCoverageTests(unittest.TestCase):
    def test_18_regions_all_get_one_where_source_provides_them(self):
        src=[]
        for i,lat in enumerate((-60.,0.,60.)):
            for j,lon in enumerate((-160.,-100.,-40.,20.,80.,140.)):
                for k in range(5):
                    src.append(station(f'S{i}{j}{k}',lat+(k-2)*.2,lon+(k-2)*.2))
        picked=balanced_global_sample(src,32)
        self.assertEqual(len(picked),32)
        self.assertEqual(len(set(geographic_bin(p) for p in picked)),18)
        self.assertTrue(all(p in src for p in picked))
        self.assertEqual(coverage_summary(src,picked)['source_occupied_regions'],18)
        self.assertEqual(coverage_summary(src,picked)['selected_occupied_regions'],18)

    def test_small_limit_selects_different_regions(self):
        src=[station(f'A{i}',45.,2.0+i*.1) for i in range(30)]
        src += [station('JP',35.,139.),station('AU',-37.,150.),station('BR',-11.,-49.),station('CA',58.,-112.)]
        picked=balanced_global_sample(src,5)
        self.assertEqual(len(picked),5)
        self.assertEqual(len(set(geographic_bin(p) for p in picked)),5)

    def test_quality_known_used_first_within_competing_cells(self):
        src=[station('A-unknown',-51.,11.,False),station('B-good',-51.1,11.1,True)]
        self.assertEqual(balanced_global_sample(src,1)[0]['station'],'B-good')

    def test_does_not_invent_stations_for_empty_regions(self):
        src=[station('J1',34.,139.),station('J2',45.,141.)]
        picked=balanced_global_sample(src,32)
        self.assertEqual(len(picked),2)
        self.assertEqual(set(x['station'] for x in picked),{'J1','J2'})
        d=coverage_summary(src,picked)
        self.assertEqual(d['selected_occupied_regions'],1)
        self.assertEqual(sum(sum(row) for row in d['selected_latitude_longitude_counts']),2)

    def test_stable_and_handles_antimeridian(self):
        src=[station('p',5.,-180.),station('q',7.,180.),station('r',10.,179.),station('s',-75.,-173.)]
        self.assertEqual(geographic_bin(src[0]),geographic_bin(src[1]))
        self.assertEqual([s['station'] for s in balanced_global_sample(src,3)],
                         [s['station'] for s in balanced_global_sample(list(reversed(src)),3)])

    def test_32_cap(self):
        src=[station(f'x{i}',(i%20)*7-65.,(i*47)%360-180) for i in range(100)]
        self.assertEqual(len(balanced_global_sample(src,TARGET_STATIONS)),32)
        self.assertEqual(balanced_global_sample(src,0),[])
        self.assertEqual(balanced_global_sample([],32),[])


class PatcherTests(unittest.TestCase):
    def test_preflight_and_idempotence(self):
        pieces={
            'scripts/validate_ionosondes.py': '''def global_sample(records, limit):
    return records[:limit]


def error_stats(x, unit):
    return []

def evaluate(raw, now=None, max_stations=16, max_age_hours=6):
    stations = global_sample(raw, max_stations)
    base = {'sampled_stations': 0, 'evaluated_stations':0}
    base['sampled_stations'] = len(stations)
    matched = stations
    base['evaluated_stations'] = len(matched)
    return base

parser.add_argument('--max-stations', type=int, default=16)
''',
            'scripts/build_prospective_skill.py': 'def build_outlook(..., horizons=HORIZONS_H, max_stations=16, ...):\n    pass',
            'scripts/build_year_archive.py': 'outlook=build_outlook(observations,iri_function,now,max_stations=12,published_at=published_at)',
            'scripts/build_tec_skill.py': "MAX_STATIONS = 16\n    station_list=nict_fixed+list(observations.get('stations', []))",
            '.github/workflows/pages.yml': "            --max-stations 16 \\\n          print('Ionosonde status:', d['status'], 'matched:', d['evaluated_stations'])\n",
            'docs/year.html': '<nav><a href="#main-skill">',
        }
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for rel,content in pieces.items():
                file=root/rel;file.parent.mkdir(parents=True,exist_ok=True)
                file.write_text(content,encoding='utf-8')
            self.assertEqual(apply(root),6)
            updated={rel:(root/rel).read_text(encoding='utf-8') for rel in pieces}
            self.assertEqual(apply(root),0)
            self.assertEqual(updated,{rel:(root/rel).read_text(encoding='utf-8') for rel in pieces})
            self.assertIn('coverage_summary(records, stations)',updated['scripts/validate_ionosondes.py'])
            self.assertIn('max_stations=32', updated['scripts/build_year_archive.py'])
            self.assertIn('MAX_STATIONS = 32', updated['scripts/build_tec_skill.py'])
            self.assertIn('--max-stations 32', updated['.github/workflows/pages.yml'])

    def test_does_not_write_partial_changes_when_anchor_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for rel in ['scripts/validate_ionosondes.py','scripts/build_prospective_skill.py',
                        'scripts/build_year_archive.py','scripts/build_tec_skill.py',
                        '.github/workflows/pages.yml','docs/year.html']:
                p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('invalid old source',encoding='utf8')
            with self.assertRaises(ValueError):
                apply(root)
            self.assertEqual((root/'scripts/validate_ionosondes.py').read_text(),'invalid old source')


if __name__=='__main__': unittest.main()
