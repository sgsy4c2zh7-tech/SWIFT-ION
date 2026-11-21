# SWIFT-ION v1.7.1 — foF2 map display repair

## What was wrong

1. The CARTO dark raster tile endpoint returned `API KEY REQUIRED` on the published page. This is unrelated to the IRI/foF2 model and means the selected basemap tiles were not rendered.
2. Japan foF2 forecasts contain only a small number of actual IRI sites (the screenshot showed 7). The original view abruptly removed pixels more than 750 km from the closest IRI site, creating detached, artificial-looking coloured disks.

## What this patch changes

- Default basemap: **OpenStreetMap (no API key)**.
- Dark basemap: the same OpenStreetMap tiles with a browser-side colour filter, no CARTO endpoint.
- Satellite: Esri World Imagery, with automatic fallback to standard OSM if repeated tile errors occur.
- Smooth fade-out of colour opacity by distance to a **valid IRI site**, with a strict 1100 km Japan boundary. This is a rendering-quality cue; it does not create additional predictions or observational detail.
- Default overlay opacity lowered to 65% so map labels are readable.
- Existing 30-minute animation, IRI-vs-TEC scenario, regions, full-screen button and GitHub workflow remain unchanged.

## Installation

Copy `docs/field.html` and `docs/shared/forecast-fade.mjs` to the same paths inside your **SWIFT-ION** repository. Optionally copy `tests/` to add regression checks. GitHub Desktop: Commit → Push. **Do not overwrite `pages.yml`**.

Suggested commit: `Fix foF2 basemap API-key error and smooth sparse-map edges`

Then Ctrl+F5 (Windows) or Shift+Reload in the browser to bypass cached HTML. Check `field.html`, change the basemap to OSM, and confirm Japan coverage.

## Science limitation

The patch does not increase the forecast's true IRI sample count. Seven Japan sites are still a sparse estimate; smooth display is not finer scientific resolution. Improving actual regional accuracy requires more IRI computations at carefully selected Japanese sites and independent verification. If the site distribution changes in the future, the fade and completeness diagnostics still work.
