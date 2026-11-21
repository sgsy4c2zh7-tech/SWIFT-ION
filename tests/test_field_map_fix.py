import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/field.html').read_text(encoding='utf-8')

class FieldMapFixTests(unittest.TestCase):
    def test_no_api_key_required_tile_provider(self):
        self.assertNotIn('basemaps.cartocdn.com',HTML)
        self.assertNotIn('api.mapbox.com',HTML)
        self.assertNotIn('tiles.stadiamaps.com',HTML)
        self.assertIn('https://tile.openstreetmap.org/{z}/{x}/{y}.png',HTML)
    def test_default_osm_and_dark_filter(self):
        self.assertIn('<option value="osm" selected>',HTML)
        self.assertIn('getContainer().style.filter',HTML)
    def test_overlay_quality_coverage_and_animation_kept(self):
        for fragment in ['coverageAlpha(nearestKm,region)','latitudeAtMercatorFraction',
                         'L.imageOverlay(', 'p.map.fitBounds', 'setInterval(()=>step(1)',
                         'ion_forecast.json', 'showSites']:
            self.assertIn(fragment,HTML)
    def test_fallback_and_attribution(self):
        self.assertIn("layer.on('tileerror'",HTML)
        self.assertIn('OpenStreetMap contributors',HTML)
        self.assertIn('p.mapWarning',HTML)

if __name__=='__main__':unittest.main()
