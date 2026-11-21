# SWIFT-ION v0.3 — SWIFT-TEC CSV import patch

Copy `scripts/` and `docs/` into the existing SWIFT-ION clone. Existing files are not overwritten by this patch.

1. On SWIFT-TEC, run the forecast and click **Export 4-day TEC to CSV**.
2. Save the downloaded CSV as `data/input/swifttec_forecast.csv` in SWIFT-ION (create folders).
3. Run `python scripts/import_swift_tec_csv.py` in the SWIFT-ION root.
4. Commit `docs/swift_tec_vtec.json` and the two patch files; push to GitHub.
5. Open `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/tec.html`.

Do not commit any sensitive data. Public repository: only use public, approved model output. The imported CSV is treated as VTEC forecasts, with correction stage **unverified**. The existing map.html remains a synthetic demonstration. No IRI calculations are claimed.

For future automation, insert `python scripts/import_swift_tec_csv.py` after `python scripts/build_map.py` in `.github/workflows/pages.yml`. This only works if the input CSV is available to the GitHub runner; a browser-only export cannot be fetched automatically from GitHub Actions. The CSV is not required for ordinary demo builds.
