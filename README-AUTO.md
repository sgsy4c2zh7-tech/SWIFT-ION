# SWIFT-ION automatic deployment patch
Copy `.github/` and `scripts/` into SWIFT-ION repo root; overwrite `.github/workflows/pages.yml`.
Commit and push. GitHub Actions will run at UTC :17 and :47, and on push/manual dispatch.

**Important**: This enables scheduling but cannot automatically obtain SWIFT-TEC's browser-generated forecast CSV unless a public HTTPS CSV endpoint exists. SWIFT-TEC currently exports CSV via a browser button, and a verified public forecast CSV URL has not been found. Do NOT configure a NOAA GloTEC observational archive URL as a SWIFT-TEC forecast URL.

When a public SWIFT-TEC CSV export URL is available, configure repository Settings -> Secrets and variables -> Actions -> Variables -> New repository variable: `SWIFT_TEC_CSV_URL`. The script validates CSV headers and values and publishes `docs/swift_tec_vtec.json` in the Pages build artifact. It does not write to SWIFT-TEC. If the URL is missing, the workflow falls back to a locally committed CSV if present, and otherwise reports the missing feed without inventing data.

For a fully hands-free SWIFT-TEC forecast, the upstream forecasting logic must be exposed as a reproducible export job or an approved endpoint; that is not implemented by this patch. Existing JSON data checked into `docs/` may be stale; the UI should show issued/valid timestamps and freshness in a future enhancement.
