# SWIFT-ION v0.9.1: KC2G time parsing / bad_shape repair

## Why
The displayed ionosonde report read 101 records but dropped all as `bad_shape`. The original `parse_stations` classified failures parsing `time` as `bad_shape`. The upstream KC2G `Measurement.time` model uses a timezone-naive SQL `DateTime`; its Marshmallow serialization may therefore supply ISO-8601 timestamps with no `Z` or UTC offset. This is a probable root cause, not yet verified against the actual 101 raw records.

## Change
- For **KC2G station records only**, interpret ISO time without an offset as **UTC** (explicit source-specific assumption); retain offset-aware conversion when supplied.
- Classify invalid timestamps separately as `bad_timestamp`.
- Add safe `schema_diagnostic` (field names/types only) to the output and the Action log when data are unusable.
- Preserve original station filters: observations 6h max age, CS minimum 70 when present, nonzero valid foF2/hmF2, location and longitude validation; no synthetic fallback.
- Include 8 focused regression tests.
- No changes to SWIFT-TEC calculation, IRI, GitHub Actions, or public HTML required.

## Install
1. Extract this ZIP. Copy `scripts/` and `tests/` **into the SWIFT-ION repo root**, overwriting `scripts/validate_ionosondes.py` only.
2. GitHub Desktop Summary: `Fix KC2G ionosonde UTC timestamp parsing`.
3. Commit to main -> Push origin. Github Actions automatically rebuilds and deploys.
4. Inspect `Ionosonde verification against IRI climatology` and https://sgsy4c2zh7-tech.github.io/SWIFT-ION/ionosonde.html.
5. If still 0 stations, look in the Action log for `Rejected record counts` and `SCHEMA_DIAGNOSTIC`, and on the page for reason-specific counts. Do not loosen time/confidence constraints before understanding the actual data.

## Validation
Local tests: `python -m unittest discover -s tests -v` (in full repo), or this patch's `python -m unittest discover -s tests -v`. The package was tested with 8 new regression cases, but access to live KC2G feed from the sandbox was unavailable, so the real fetch/IRI run remains to be verified by GitHub Actions.

## Attribution / operational limitations
Data from KC2G derived from GIRO/INGV. Respect noncommercial/attribution requirements. foF2/hmF2 is **IRI model vs observed station** at measurement time, NOT a validated future forecast. Source datetime policy is a deliberate assumption that must be rechecked if upstream source changes.
