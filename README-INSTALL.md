# SWIFT-ION v0.9 — Ionosonde observational comparison

**Includes a critical fix:** `.github/workflows/pages.yml` in the connected SWIFT-ION repository contained unresolved Git conflict markers again. This package **replaces the entire file** with a clean workflow. Do not merge it line-by-line.

## Installation (GitHub Desktop)

1. Extract the ZIP.
2. Copy all 4 folders `.github`, `docs`, `scripts`, `tests` into the root of your local `SWIFT-ION` repository. Confirm overwrite when prompted. Do **not** copy into the upstream SWIFT-TEC repository.
3. Open `.github/workflows/pages.yml` and confirm `<<<<<<<`, `=======`, `>>>>>>>` are absent.
4. Commit summary: `Fix Pages workflow and add GIRO ionosonde validation`.
5. **Commit to main → Push origin**. Check `Actions → Build and publish SWIFT-ION`.
6. Check `Ionosonde verification against IRI climatology`, then open `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/ionosonde.html`.

If network access to KC2G fails or no recent station records are available, `ionosonde_validation.json` is still produced with status `SOURCE_UNAVAILABLE` or `NO_USABLE_OBSERVATIONS`, and the screen displays *no results*, not fabricated error statistics. Existing SWIFT-TEC and IRI calculation steps remain unchanged in their underlying scripts.

## What is scientifically measured?

IRI is run at **each ionosonde observation time and position** (up to 16 geographically dispersed stations / run). Only then is the estimated F2 critical frequency (`foF2`) and the approximate sampled-maximum peak altitude (`hmF2`) compared with station measurements. This is climatological-model discrepancy, **not proof of forecast skill**. The source is a public KC2G station feed derived from GIRO/INGV, not the official authenticated DIDBase raw feed. It may reflect autoscaled or manually validated data.

The license is GIRO CC BY-NC-SA 4.0 and Rules of the Road. This is strictly a non-commercial, educational/research evaluation and not for operational decisions. Acknowledge KC2G, GIRO and each station data provider: see `docs/IONOSONDE_VALIDATION.md`.

## Data and website

- Python: `scripts/validate_ionosondes.py`
- Tests: `tests/test_ionosonde_validation.py`
- Output: `docs/ionosonde_validation.json` (generated at Actions runtime; not committed)
- UI: `docs/ionosonde.html`
- Source/license documentation: `docs/IONOSONDE_VALIDATION.md`
- Workflow: `.github/workflows/pages.yml`

The first Actions run may reveal external service access or IRI runtime limitations. The patch passed local parser/statistical tests and syntax checks; **it has not been verified running end-to-end on GitHub Actions**.
