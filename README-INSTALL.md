# SWIFT-ION v0.6 IRI pilot

This is a **real IRI model integration adapter**, not a verified production deployment. `iri2020` runtime has NOT been tested in this environment; the package and its Fortran backend must be installed and validated separately. No synthetic values are substituted.

## Installation
Copy `scripts`, `docs`, `tests` into the repository root. Do not replace `.github/workflows/pages.yml` yet. Existing SWIFT-TEC live VTEC automation remains intact.

After the existing GitHub Actions pipeline generates `docs/swift_tec_vtec.json`, run in a Python environment with `iri2020` available:

```
python -m pip install iri2020
python scripts/build_ionosphere.py --max-cells 24 --max-frames 1
```

`iri2020` may require CMake and Fortran toolchain, and the actual xarray schema should be checked against `extract_iri_profile`. Commit `docs/ionosphere.json` and publish to test `ionosphere.html` only after successful computation. The model uses 100–600 km, 20 km altitude steps and explicitly does NOT claim full TEC assimilation or D/E/F1 layer predictions. `foF2` derives from NmF2, not from an independently validated ionosonde output. hmF2 is grid-sampled and peak-at-boundary is flagged.

This is a limited 24-cell/1-frame proof of concept; it does NOT produce a global map. It intentionally does not alter the existing scheduled workflow because failing to install IRI would otherwise stop all SWIFT-TEC publishing. After verification, add an optional IRI job with caching and error isolation.
