# SWIFT-ION v1.2 integrated public-research suite

This is a **patch** for the existing `sgsy4c2zh7-tech/SWIFT-ION` repository, not a full standalone copy. Apply by copying `.github`, `scripts`, `docs` and `tests` into the repository root and overwriting matching files. Commit and push to `main` using GitHub Desktop.

## Components delivered

1. **30-minute full-native-grid VTEC animation**: `docs/animate.html`, `docs/shared/forecast.js`, `scripts/animation_format.py`, `scripts/build_live_swifttec.py`, `scripts/check_animation.py`. The existing upstream SWIFT-TEC `runForecast()` still executes read-only; SWIFT-ION exports its full 30-minute lat/lon grid into time-indexed JSON chunks. This data is an **unvalidated experimental SWIFT-TEC forecast**, not an observation. Its ML-correction output stage has not been independently verified. Site URL `/animate.html`.
2. **Public sample-route analysis**: `docs/impact.html`. Four deliberately generic great-circle sample journeys; route time interpolation (30-minute forecast time axis), spatial bilinear interpolation, sampled VTEC, approximate GPS L1 vertical first-order group delay, and changes of consecutive samples normalized to 100 km. Consecutive-sample changes include temporal variation; they are not a pure spatial gradient. No actual flight plan, avoidance recommendation, GNSS availability, HF link performance, radiation exposure, or tactical operational scoring. Site URL `/impact.html`.
3. **Space weather situational reference**: `scripts/build_space_weather.py` and `docs/ops.html`. NOAA SWPC `noaa-scales.json` G/S/R categories **current only**; source time and fetch time recorded, stale source not presented as current. Distinct labels for unavailable HF performance, route radiation, radar and satellite-link capability. Site URL `/ops.html`.
4. **3D IRI height slices**: `scripts/build_density_slices.py` and `docs/globe.html`. Sparse IRI model profiles interpolated to display positions and selected altitudes; CesiumJS point-shell visualization. This is **not an independent 3-D forecast nor 3-D observation**; no ionosphere refraction ray tracing or D-region. Site URL `/globe.html`.
5. **Updated front page**: `docs/index.html` links all these panels and the existing science and accuracy pages.

## Existing functionality explicitly preserved

- `docs/swift_tec_vtec.json` two-hour sampled contract; IRI integration consumes it without code changes.
- Current `scripts/build_ionosphere.py`, `scripts/build_quality_report.py`, and `scripts/validate_ionosondes.py` and their existing output contracts.
- `scripts/build_year_archive.py`, `swift-ion-history` branch, rolling 365-day foF2/hmF2 baseline verification, CSV and JSON annual output.
- Existing GitHub Pages publication and scheduled execution at UTC minute 17/47.

## Deploy

1. Back up `.github/workflows/pages.yml` and `scripts/build_live_swifttec.py` before overwriting.
2. Extract patch ZIP and copy its `.github`, `scripts`, `docs`, `tests` folders into the local repository root (same level as existing `README.md`). Overwrite matching files; don't delete other files.
3. GitHub Desktop Summary: `Add global animation, aviation research and 3D ionosphere views`.
4. Commit to main / Push origin.
5. Confirm the GitHub Actions steps **Calculate SWIFT-TEC VTEC forecast and 30-minute animation**, **Fetch NOAA SWPC current scales**, **Export IRI density slices for 3D globe**, **Record prospective IRI forecasts and score a rolling 365 days**, **Deploy GitHub Pages**.
6. Open `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/` and navigate to the new pages.

## Known limitations / review points

- New scripts were verified locally using 10 Python unit tests, JavaScript syntax checks, a shared JS interpolation test and workflow YAML parsing, but **the full GitHub Actions end-to-end job, actual SWIFT-TEC upstream browser calculation, and Cesium web rendering were not run in the local container**.
- The upstream SWIFT-TEC calculation nominally produces 30-minute frames for 120 hours (typically 241 inclusive timestamps). Actual valid frame count is checked at runtime; site rendering uses whatever the model produces.
- IRI altitude display uses 5 generated IRI times, not the 241 VTEC times. Intermediate IRI time states have not been synthesized.
- The 3D globe requires WebGL and CesiumJS CDN; map background uses OpenStreetMap; NOAA feed requires internet access during Actions.
- No restricted flight routes, sensitive asset positions, mission-specific frequencies or unapproved operational data should be placed on publicly hosted GitHub Pages.
- Model predictions and present NOAA conditions are not validated warnings for communication or navigation availability. The output must not be used for safety/operational decisions.
- Third-party data, OSM tiles and CesiumJS may have independent attribution/licensing and service-usage requirements; respect them. Existing KC2G/GIRO-derived components remain subject to non-commercial/attribution terms.

## Package contents

```
.github/workflows/pages.yml
scripts/animation_format.py
scripts/build_live_swifttec.py
scripts/check_animation.py
scripts/build_density_slices.py
scripts/build_space_weather.py

docs/index.html
docs/animate.html
docs/impact.html
docs/ops.html
docs/globe.html
docs/shared/forecast.js

tests/test_animation_format.py
tests/test_suite.py
```
