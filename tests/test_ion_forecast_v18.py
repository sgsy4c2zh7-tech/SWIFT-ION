"""v1.8 spatial-density and two-cadence verification, mock IRI only."""
import sys, math, unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import build_ion_forecast as m


class TestV18SpatialSamples(unittest.TestCase):
    def test_120_sites_with_40_japan(self):
        sites = m.locations({}, max_sites=120, japan_sites=40)
        self.assertEqual(len(sites),120)
        self.assertEqual(len(set(sites)),120)
        self.assertTrue(all(m.in_japan(*p) for p in sites[:40]))
        self.assertTrue(all(not m.in_japan(*p) for p in sites[40:]))
        self.assertTrue(all(-90<=a<=90 and -180<=b<=180 for a,b in sites))

    def test_japan_coverage_and_global_spacing(self):
        sites = m.locations({}, max_sites=120, japan_sites=40)
        # Japan sites are not only Tokyo, and include each of the 9 cities.
        for city in m.JAPAN_SITES:
            self.assertIn(city,sites)
        for lat,lon in [(25,125),(30,135),(35,145),(42,142),(45,125)]:
            closest=min(m.distance_km((lat,lon),q) for q in sites[:40])
            self.assertLess(closest, 650)
        # All major longitudes must be represented outside Japan.
        self.assertTrue(any(x[1]<-130 for x in sites[40:]))
        self.assertTrue(any(-30<x[1]<30 for x in sites[40:]))
        self.assertTrue(any(x[1]>130 for x in sites[40:]))

    def test_two_cadences_and_failure_contract(self):
        start=datetime(2026,11,21,tzinfo=timezone.utc)
        times=[start+timedelta(minutes=30*i) for i in range(49)]
        sites=m.locations({},max_sites=12,japan_sites=4)
        count=0
        def provider(t, lat, lon):
            nonlocal count
            count+=1
            return m.PROFILE_ALTITUDES,[1e10+9e11*math.exp(-((z-325)/130)**2) for z in m.PROFILE_ALTITUDES]
        anchors, errors, attempts=m.build_anchors(times,sites,provider,6,japan_site_count=4,global_hours=12)
        # 24-hour mock series: Japan t=0,6,12,18,24 = 5; global t=0,12,24 = 3.
        self.assertEqual(attempts,4*5+8*3)
        self.assertEqual(count,attempts)
        self.assertEqual(len(anchors),12)
        self.assertFalse(errors)
        self.assertEqual(len(anchors[0]['indexes']),5)
        self.assertEqual(len(anchors[4]['indexes']),3)
        self.assertAlmostEqual(m.interpolate_anchors(1,anchors[4]['indexes'],anchors[4]['pairs'])[1],anchors[4]['pairs'][0][1],places=4)

    def test_missing_iri_anchor_drops_site(self):
        start=datetime(2026,11,21,tzinfo=timezone.utc)
        times=[start+timedelta(minutes=30*i) for i in range(25)]
        sites=[(35.68,139.76),(43.06,141.35)]
        def provider(t, lat, lon):
            if lat>40 and t.hour==6:
                raise RuntimeError('data missing')
            return m.PROFILE_ALTITUDES,[1e11 for _ in m.PROFILE_ALTITUDES]
        anchors,errors,_=m.build_anchors(times,sites,provider,6,japan_site_count=2,global_hours=12)
        self.assertEqual(len(anchors),1)
        self.assertTrue(errors)

if __name__=='__main__':unittest.main()
