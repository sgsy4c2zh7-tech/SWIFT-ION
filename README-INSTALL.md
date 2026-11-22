# SWIFT-ION v2.2 — NICT 4-site foF2 research validation and training bridge

## Install

Copy `.github/`, `scripts/`, `docs/`, `tests/` and `nict_import/` from this ZIP into the SWIFT-ION repository root. Commit and Push using GitHub Desktop.

Commit Summary: `Add NICT four-station foF2 observation validation and training bridge`

## Operation and limits

- Archives verified-format numerical CSV with 4 NICT site IDs, explicit UTC or JST (converted to UTC), foF2 in MHz, provenance. There are **NO synthetic observations in this patch**.
- Evaluates only previously issued, archived snapshots against later NICT observations, matching ±15 minutes and within 15 km of official station coordinates; stores `nict_matches` and `nict_observations` in existing `swift-ion-history` 365-day branch.
- NICT station coordinates are always included in newly issued `tec_outlooks` so an NICT validation sample can later be matched even when GIRO/KC2G lacks these stations.
- Existing empirical / AI trainer uses only archived STANDARD-quality prospective matches and chronological holdout; future-observation leakage is prohibited.
- Displays latest 7 days of imported NICT observations on `docs/nict_compare.html` and station-by-station accuracy at `docs/nict_skill.html`. If no data are available, the website says so explicitly.
- Default frequency: GitHub Actions schedule; source import happens before learning the new model. GitHub Pages build is unchanged.

**Important:** NICT's archive landing page does not expose a verified machine-readable download URL/format in our environment. This ZIP does NOT invent an API or claim unattended direct NICT downloads are already working. To ingest observations NOW, convert the numerical NICT export to the normalized format in `nict_import/README.md` and commit those CSV files. To enable scheduled downloads after verifying numerical URLs, add the GitHub Actions secret `NICT_AUTO_SOURCE_URLS` with a JSON mapping (examples of *structure only*):

    {"WAKKANAI":"https://wdc.nict.go.jp/ACTUAL_VERIFIED_NUMERIC_FILE.csv"}

This example is NOT a real download path and must not be used as is.

Official source: https://wdc.nict.go.jp/Ionosphere/en/archive/isdj_auto_txt.html
Attribution: WDC for Ionosphere and Space Weather, Tokyo, National Institute of Information and Communications Technology. The NICT data policy requires appropriate acknowledgement on publications; confirm data redistribution permissions before making auto-ingested raw data public. Automatically scaled parameters are preliminary and should be quality-screened before stronger claims.

## Verify

- `python -m unittest discover -s tests -p 'test_nict_bridge.py' -v`
- GitHub Actions step `Ingest NICT four-station observations and score prior forecasts`
- `docs/nict_fof2_status.json` (`AWAITING_NICT_NUMERIC_CSV` when none imported)
- `docs/nict_fof2_4station.csv` (header-only when none imported)
- `docs/nict_skill.html` for station scores.

Existing IRI baseline and three-stage / TEC 365-day scores remain separate; source-mixed training rows carry source labels; no historical forecast backfilling is done.
