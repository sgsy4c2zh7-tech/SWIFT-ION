# SWIFT-ION v1.6 — IRI+TEC Forecast Cinema / foF2 Route

## What this patch adds

- **30-minute forward-time ionosphere scenario** (`scripts/build_ion_forecast.py`): the already-published SWIFT-TEC 30-min VTEC forecast supplies time and column TEC; **future-time IRI-2020** supplies sparse vertical profiles. IRI is calculated at 12-hour anchors (14 global/Japan sites); at the intervening 30-minute valid times, the profiles are **linearly interpolated in time**, not independently recomputed. This is NOT a validated new physical forecast.
- **Experimental foF2 scenario**: a restricted uniform positive scaling of Ne(h), only for sites where VTEC/IRI 100–2000 km partial TEC ratio is in `[0.5,2.0]` and IRI topside truncation is small. The scenario foF2 is `foF2_IRI * sqrt(scale)`; **hmF2 is never moved by TEC scaling**. Unavailable corrections remain null.
- **foF2 / hmF2 / Ne cinematic map** (`docs/field.html`), with 30-minute playback, clock and fullscreen.
- **foF2 flight-route cinema** (`docs/route.html`, `docs/shared/route-forecast.mjs`): public/illustrative geographic paths, distance-vs-foF2 plot, density curtain, per-point UTC. You may choose *same-UTC snapshot* or *hypothetical travel-time passage*; the latter shifts the model sampling time along the path by a user-entered flight duration. Includes fullscreen and 30-min replay. **It is not HF/MUF performance or aircraft navigation guidance.**
- **3D globe / GAIA multi-layer video** (`docs/explorer.html`, `docs/shared/gaia3d-app.mjs`): future foF2, hmF2, Ne shells, voxel, isosurface, vertical section all share the 30-minute timeline. OpenStreetMap / Esri World Imagery / grid basemap. Extra playback controls remain available in fullscreen.
- **Original SWIFT-TEC VTEC animation fullscreen wrapper** (`docs/animate_fullscreen.html`): opens the existing `docs/animate.html` without modifying its NOAA fetching or animation engine.
- **Simplified homepage** (`docs/index.html`): four core forecast views prominent, old duplicate demo pages omitted from main cards, verification and yearly history still linked and unchanged.
- **Original workflow preserved**, plus only one downstream forecast export step and one diagnostics artifact (`.github/workflows/pages.yml`).

## Install with GitHub Desktop

1. Extract this ZIP.
2. Copy `.github`, `docs`, `scripts`, `tests` into the root of the **SWIFT-ION** repository (not SWIFT-TEC). Overwrite matching files.
3. Commit summary: `Add 30-minute foF2 route forecast cinema and synchronized 3D playback`.
4. Push main, then inspect Actions step `Build 30-minute ionosphere forecast cinema`. The existing `Calculate SWIFT-TEC...`, `Build GAIA-style...`, `Record prospective...`, `Commit 365-day history` steps remain.
5. Once Pages deployment succeeds, use:
   - `/` central dashboard
   - `/animate_fullscreen.html` VTEC original player with fullscreen
   - `/field.html` foF2 / hmF2 / Ne 30-min playback
   - `/route.html` foF2 flight-route playback and Ne curtain
   - `/explorer.html` 3D layered globe + foF2/ hmF2 animation
   - `/year.html` original 365-day skill history

## Boundaries, provenance and status

- This does **not** rewrite SWIFT-TEC, NOAA, ISEE source, the KC2G comparison, or the `swift-ion-history` branch.
- ISEE Japan VTEC is an archived observation product, not a Ne(h) measurement or a future ISEE forecast. The historical Japan mode remains separate from the future IRI+TEC mode.
- `docs/ion_forecast.json` is always explicitly marked **unvalidated**. If the IRI model cannot load, the export writes an `IRI_UNAVAILABLE` status instead of fake numbers; the old Pages workflow should still continue.
- All model pages use sparse IRI spatial interpolation. foF2 from IRI NmF2 is a proxy, while hmF2 is a height-grid peak; the actual temporal dynamics, uncertainty and independent future skill are **not proven**.
- Old accuracy history remains for the separately issued IRI baseline, **not** automatically for these new TEC-linked scenario outputs. No historical accuracy is asserted for v1.6.
- Public illustrative routes only. Do not upload or embed private flight paths, operational frequencies, system weaknesses or mission data in public GitHub Pages.

## Tests

Run `python -m unittest discover -s tests -v` (new Python 6 tests, including a Node-executed JS interpolation/route test), or `node tests/test-route-forecast.mjs`. Browser CesiumJS and Leaflet still require Internet; deployment/rendering must be checked on the published Pages site.
