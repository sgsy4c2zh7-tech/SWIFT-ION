# SWIFT-ION v1.5 — GAIA-style Multilayer / Voxel / Isosurface Explorer

## Installation (preserves existing workflow)

1. Back up your current `SWIFT-ION/docs/explorer.html` if desired.
2. Extract this ZIP directly into the **root** of your existing `SWIFT-ION` repository, overwriting only matching files:
   - `docs/explorer.html` (new 3D Cesium UI)
   - `docs/shared/gaia3d.mjs` (math / IDW / marching tetrahedra)
   - `docs/shared/gaia3d-app.mjs` (Cesium UI/rendering)
   - `tests/test_gaia3d_js.py` (Python discovery wrapper for JS tests)
   - `tests/test-gaia3d.mjs` (Node.js numerical tests)
3. Do **NOT** replace your `.github/workflows/pages.yml`. This patch deliberately includes **no workflow file**.
4. Commit in GitHub Desktop: `Add GAIA-style multilayer shells, volumetric voxels and IRI isosurfaces`
5. Push to main and wait for your existing GitHub Pages workflow to finish.
6. Open: `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/explorer.html`

## Required existing pipeline

The published `docs/explorer_data.json` from SWIFT-ION v1.4 is required.
- schema `swift-ion-explorer-v1.4`
- `global_frames[].sites[]` with `lat`, `lon`, `ne_log10_m3[]`
- `japan.frames[].iri_sites[]` computed at the exact ISEE observation UTC
- `japan.frames[].vtec` for **separately shown** observed-type ISEE VTEC [TECU]
- `metadata.altitudes_km[]` (representative altitudes 100–1000 km)

NOAA scripts, upstream SWIFT-TEC, 365-day history and ISEE/IRI generator are **not modified**.

## Features

- **Single-height:** a semi-transparent, continuous IRI electron-density texture on a Cesium rectangle at a chosen height, with fixed color scale `log10 Ne = 8.0–12.8 m^-3`.
- **Four shells:** checkable E (~125 km), F1 (~190 km), F2 (~300 km), topside (~650 km) representative height slices. Shared time and fixed legend, individual checkbox + individual opacity sliders + global opacity.
- **Route curtain:** view the same selected IRI model time along a public/illustrative route. Great-circle route sampling, IDW interpolation; altitude-vs-distance section chart and 3D translucent curtain.
- **Voxel preview:** up to ~900 coarse 3D box geometry instances filtered by the chosen electron density threshold. This is an IRI interpolation visualization, not measured 3D tomography.
- **Isosurface:** marching tetrahedra on a reduced lat/lon/alt grid. Draw a mesh for selected `log10 Ne` threshold. This is true geometry extraction from a *model-interpolated field*, not a new assimilative physical product.
- **Japan:** existing v1.4 ISEE VTEC readout, source age, and same-UTC IRI comparison retained. City selection includes locations across Japan.

## Scientific cautions

- IRI-2020 **climatology** provides electron-density height profiles, not a verified forecast.
- ISEE archived VTEC is a vertically integrated quantity; it is **not** 3D observed electron density. ISEE/VTEC and IRI/Ne are kept separate.
- Smooth colors, interpolation, and isosurfaces do not add information beyond the sparse IRI sample sites. Near boundaries and over gaps, spatial uncertainty can be large.
- F1 may not be a distinct physical peak at all times; shell labels are approximate altitude bands.
- Not for operational aviation, GNSS, HF, military or safety decisions.
- Cesium 3D and OpenStreetMap imagery require an internet-connected browser supporting WebGL.

## Tests

```bash
node --test tests/test-gaia3d.mjs
python -m unittest discover -s tests -p 'test_gaia3d_js.py' -v
```

The numerical tests exercise altitude interpolation, nearest site, source clipping, palette transparency, great-circle routes, and marching-tetrahedra isosurface generation. They do not certify the full Cesium visual outcome in a deployed browser. The existing workflow's Python test discovery automatically runs the `test_gaia3d_js.py` wrapper if Node.js is installed (GitHub Ubuntu hosted runners include Node.js).

## If the display fails

1. Open the `explorer.html` page and inspect its blue status panel.
2. Check that `explorer_data.json` is available (GitHub Actions `Build GAIA-style IRI and ISEE Japan explorer` stage).
3. Check browser developer console for Cesium/CDN/WebGL problems. Try **Single Height** and **Lightweight** resolution first.
4. If there are no ISEE/IRI regional frames, Japan mode is unavailable and the interface falls back to Global IRI without inventing observed data.

### Restore previous version

Replace just `docs/explorer.html` with your previous version and remove `docs/shared/gaia3d.mjs` and `docs/shared/gaia3d-app.mjs` if no longer needed. The scientific data generation and workflow remain untouched.
