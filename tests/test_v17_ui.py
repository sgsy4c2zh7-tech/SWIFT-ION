import unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]

class InterfaceCompatibility(unittest.TestCase):
 def test_field_has_base_map_and_overlay(self):
  s=(BASE/'docs/field.html').read_text()
  for x in ('id="fieldMap"','id="mapStyle"','id="heatAlpha"','L.imageOverlay(','p.heat.setBounds(','latitudeAtMercatorFraction'):
   self.assertIn(x,s)
 def test_field_maintains_forecast_options(self):
  s=(BASE/'docs/field.html').read_text()
  for x in ('value="fof2"','value="hmf2"','value="tec"','value="ne"','value="global"','value="japan"','value="iri"','value="tec"','ion_forecast.json','id="seek"','id="fullscreen"'):
   self.assertIn(x,s)
 def test_cesium_has_views_and_side_controls(self):
  s=(BASE/'docs/explorer.html').read_text()
  for x in ('id="scene3d"','id="scene2d"','id="scene25d"','id="sidePreset"','id="topPreset"','id="cameraPitch"','id="cameraHeading"','id="cameraRange"'):
   self.assertIn(x,s)
 def test_cesium_camera_uses_supported_modes(self):
  s=(BASE/'docs/shared/gaia3d-app.mjs').read_text()
  for x in ('morphTo2D','morphTo3D','morphToColumbusView','Cesium.HeadingPitchRange','camera.lookAt(','lookAtTransform','scene.morphComplete'):
   self.assertIn(x,s)
 def test_existing_synchronization_kept(self):
  s=(BASE/'docs/shared/gaia3d-app.mjs').read_text()
  for x in ('ion_forecast.json','explorer_data.json','modelVariant','HEIG'+'HT_LAYERS','drawProfile','drawSection','drawIseeMap','requestFullscreen'):
   self.assertIn(x,s)

if __name__=='__main__':unittest.main()
