# SWIFT-ION v1.8 — Dense foF2 IRI Grid Patch

This is an overwrite-only patch for the existing **SWIFT-ION**, not the SWIFT-TEC repository.

## What changed

1. **Real IRI2020 sampling sites: 14 → up to 120**.
   - Japan: up to **40 sites**, including nine public-city geographic anchors, with balanced points over the Japan-area grid (23–47°N, 121–152°E).
   - Rest of globe: **80 near-equal-area sites** from a spherical candidate lattice and max-min great-circle selection.
   - Individual IRI calls are made at these positions. Geographic spreading is **not** synthetic IRI data or extra independent observations.
2. **Temporal anchors:** Japan every **6 hours**, other global points every **12 hours**. Both are interpolated onto **the existing 30-minute VTEC timeline**, preserving all 241 time frames when provided by SWIFT-TEC.
3. **Map visibility:** the foF2/hmF2/Ne player reports requested and valid Japan/global site counts, with a smaller distance-limited spatial extrapolation mask (Japan max 750 km; other globe max 3000 km). No fill beyond the mask; samples are still spatial interpolations.
4. **Unchanged:** NOAA data handling, SWIFT-TEC upstream repository, 30-min source VTEC forecast, original 3D/route/ionosonde pages, ISEE archived VTEC, independent 365-day accuracy history and GitHub Pages deployment actions.
5. **No claim of new independent physics or skill:** foF2 is derived from IRI F2-band NmF2. TEC-linked foF2 is a bounded and explicitly unvalidated uniform vertical-density scaling scenario. hmF2 is not updated by TEC.

## Install in GitHub Desktop

1. Extract ZIP.
2. Copy the directories `.github`, `scripts`, `docs`, `tests` into **SWIFT-ION repository root** and overwrite matching files. Do not copy them to `tec_tool_globalgrid_f107_copy`.
3. Commit summary: `Increase Japan and global IRI sampling for foF2 maps`.
4. Push the main branch.
5. GitHub **Actions → Build and publish SWIFT-ION**: check the step **Build 30-minute ionosphere forecast cinema**. It should log `iri_sites` near 120, with Japan ~40 and other global ~80 valid locations. Inspect any `model_failures` and fallback status if fewer sites succeed.
6. Check `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/field.html` with **Ctrl+F5**. Switch between Japan and global and select **IRI基準**. The site count should be much larger than before. foF2 route cinema and GAIA 3D read the same updated `ion_forecast.json` automatically.

## Important: Computational cost

For 241 forecast frames (~5 days), this configuration attempts up to **1,720 actual IRI calls**:
- Japan 40 sites × 21 anchor timestamps = 840 calls
- Rest of globe 80 sites × 11 anchor timestamps = 880 calls

This is **approximately 11×** the previous 14-site/12-hour model calls. It may exceed the existing GitHub Actions job's **55-minute limit** depending on IRI runtime and upstream latency. **Actual 2026-11-21 GitHub Actions runtime has not been tested.** The full mock model run produces ~17MB JSON, which also increases browser load time.

If it takes too long, edit only the `Build 30-minute ionosphere forecast cinema` step in `.github/workflows/pages.yml`:

```yaml
--max-sites 96 \
--japan-sites 32 \
--anchor-hours 6 \
--global-anchor-hours 12
```

Or use `--max-sites 80 --japan-sites 28` for another conservative fallback; the spatial quality improvement over 14 sites remains significant. **Do not increase the whole workflow's timeout without considering the 30-minute schedule and queueing.**

## Safety and scientific distinctions

- No ISEE VTEC observation has been converted into a measured 3D Ne(h) field.
- Regional Japanese measurements may be delayed; this patch doesn't use future-dated observations.
- FoF2 is *not* a proven HF link availability metric and does not predict mission system performance.
- Display smoothness is limited by the spacing of IRI model computations. Denser sampling reduces interpolation artifacts; it does **not prove** a higher scientific prediction hit rate.
- No synthetic model outputs are published as forecasts. If fewer than 65% of 120 sites yield complete real IRI anchors, the optional forecast publishes an explicit `IRI_UNAVAILABLE` status instead of implying adequate coverage.

## Local checks

```bash
python -m unittest discover -s tests -v
node tests/test-forecast-fade.mjs
```

Tests use a **mock IRI provider only**. A 241-frame synthetic fixture tested output timing, model sampling count and serialization, not live IRI physics.
