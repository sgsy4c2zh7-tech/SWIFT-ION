# SWIFT-ION — research prototype v0.1

Independent, public-data-only ionospheric research toolkit. **Does not modify SWIFT-TEC.**

## Status
This release is a **working demonstration scaffold**, not a validated ionospheric forecast. The included sample profile and map are **synthetic**. No live IRI/TIE-GCM calculations, HF optimal-frequency recommendations, GNSS reliability forecasts, or operational alerts are claimed. The five modules provide baseline calculations, data contracts, and explicit unavailable states.

## Run (Python 3.11+, standard library only)

```bash
python -m unittest discover -s tests -v
python scripts/build_demo.py
```
Open `docs/index.html` in a browser, or enable GitHub Pages from GitHub Actions after the workflow runs. The workflow builds and publishes a demonstration dashboard on pushes to `main` if Pages permissions are enabled.

## SWIFT-TEC read-only import
Place a **public, approved** JSON export at `data/input/swift_tec.json` matching `docs/SWIFT_TEC_CONTRACT.md`, then run `python scripts/check_input.py`. No endpoint is guessed; existing source export schema must be verified before live synchronization. The reader never writes to SWIFT-TEC.

## Roadmap
1. IRI profile adapter + D/E/F1/F2 diagnostics; physical peak detection and validation.
2. Public/synthetic-route HF propagation (MUF/LUF/FOT require full propagation model, antenna/noise assumptions).
3. GNSS first-order ionospheric group delay, then uncertainty and scintillation models.
4. Satellite link and radar ionospheric effects with geometry and frequency inputs.
5. Space-weather hazard thresholds, provenance and uncertainty.

TIE-GCM is **not run on GitHub Actions** in this version. Precomputed scenario support will be added after an appropriate public dataset is selected. D-region, topside/plasmasphere and storm-time physics require dedicated treatments. Never treat VTEC alone as a unique Ne(h) profile.

Public repository: do not upload mission routes, operational radio configurations, sensitive locations, credentials, or restricted data.
