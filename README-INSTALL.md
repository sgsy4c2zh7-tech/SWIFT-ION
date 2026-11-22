# SWIFT-ION v2.0.1 — NICT-style foF2 chart axes

## What is changed
- `docs/nict_compare.html`: NICT-style 6-day UTC viewing window (default), 48h/96h/full-source options, station-specific visible-range MHz axes, date and hour labels.
- `docs/shared/axis-plots.mjs`: add an optional one-MHz y-axis and UTC day/hour grid mode. Other pages keep their existing axis behavior.
- `tests/test_nict_axis_window.mjs`: test 6-day UTC windows and one-MHz boundaries.

No forecast-generation code, GitHub Actions, NICT import, Excel export, or annual-accuracy data is modified.

## Install
1. Extract the ZIP.
2. Copy `docs` into the top level of your local `SWIFT-ION` repository, overwriting the two same-named files.
3. Optionally copy `tests` to retain the new test.
4. Commit in GitHub Desktop with:
   `Use NICT-style 6-day UTC charts with 1 MHz foF2 axes`
5. Push and reload `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/nict_compare.html` with Ctrl+F5.

## Research interpretation
- Each station determines its own vertical scale from its forecast/CSV observation values **within the visible UTC window**. The labels are at integer MHz values, e.g. 4, 5, 6 ... 14 MHz.
- The six-day UTC window begins at 00:00 UTC on the first date present in the published forecast. It is a **display duration**, not a claim that six days of forecast data exist.
- Native SWIFT-ION forecast data currently cover approximately five days. The remaining portion of the six-day plotting window is blank. No missing day is calculated or fabricated.
- The horizontal axis draws UTC dates (MM/DD), 6-hour guide lines by default, and hour labels when the card is wide enough. It may suppress some text labels on small screens while preserving the gridlines.
- Observations remain absent until an actual NICT-derived CSV is uploaded. This is not a validated forecast skill report.

## Validation
`node tests/test_nict_axis_window.mjs`
HTML module JavaScript and shared module were also checked with `node --check`. A full browser rendering check was not possible because this environment blocks local HTTP browser navigation.
