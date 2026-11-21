# SWIFT-ION v0.7: Global IRI + TEC what-if scenario

This patch is based on repository `sgsy4c2zh7-tech/SWIFT-ION` as of 2026-11-21.

## Install

1. Extract the ZIP.
2. Copy `.github/`, `scripts/`, `docs/`, `tests/` to the root of local SWIFT-ION, allowing overwrites.
3. GitHub Desktop commit message: `Add global IRI mapping and TEC sensitivity study`.
4. Push to `main`, open **Actions > Build and publish SWIFT-ION**.
5. On success, browse `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/ionosphere.html`.

## Verification

The GitHub job runs the existing Playwright SWIFT-TEC forecast calculation, installs IRI-2020 and its Fortran dependencies, calculates 72 spatially distributed actual IRI profiles for each of three forecast valid times, and interpolates the IRI diagnostics to the *684 published SWIFT-TEC sample cells*. The actual IRI profiles, interpolated map cells, and TEC-scaling sensitivity scenarios are separately identified.

- IRI profiles: 100–2000 km every 25 km; D layer excluded.
- UTC selected times: first, middle and final available SWIFT-TEC time frame.
- Assumption for experimental scaling: 100–2000 km partial IRI TEC approximates full observed/modelled SWIFT-TEC VTEC; this misses below 100km and above 2000km (notably plasmaspheric TEC). Scaling allowed only when VTEC/IRI partial-TEC lies in [0.5, 2] and top boundary density is <10% of F2 peak. This is a **sensitivity test**, not validated assimilation or forecast.
- Uniform density scaling changes NmF2 and foF2 but cannot change hmF2; this is explicitly labelled.
- Global grid is geographically interpolated using five-nearest inverse-distance weighted actual IRI results. The map labels actual IRI cells vs interpolations; no claim of real IRI computation at every grid cell.
- Upstream SWIFT-TEC code is **read-only**; ML stage remains unverified.
- The web map's colors are fixed-scale so time-to-time comparisons do not rely on automatic color rescaling.

## Local tests (no IRI dependency needed)

`python -m unittest discover -s tests -v`

## Limitations

GitHub Actions has **not** been run here. IRI runtime, input freshness, future-date indices, and runtime constraints must be checked on the first run. If IRI fails, deployment fails rather than publishing invented electron densities. 72 profiles * 3 time points may be costly; adjust `--max-cells` and `--max-frames` in `pages.yml` and matching validation thresholds if necessary. Scheduled jobs can be delayed by GitHub.

The page `ionosphere.html` is an IRI + TEC model-research dashboard, not an operational HF or GNSS prediction. The SWIFT-TEC VTEC raw fields remain forecast values with unverified correction stage.
