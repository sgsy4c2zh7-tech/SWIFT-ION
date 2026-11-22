# SWIFT-ION v1.9 — NICT four-station comparison & Excel export

## Installation (GitHub Desktop)
1. Extract the ZIP.
2. Copy the `docs/` folder into the root of your `SWIFT-ION` repository and merge; replace `docs/index.html`.
3. Commit and push. Suggested Summary: `Add four-station NICT comparison and Excel route export`.
4. Wait for your existing GitHub Pages deployment, then open:
    - https://sgsy4c2zh7-tech.github.io/SWIFT-ION/nict_compare.html
    - https://sgsy4c2zh7-tech.github.io/SWIFT-ION/route_excel.html
    - https://sgsy4c2zh7-tech.github.io/SWIFT-ION/field_customize.html

No modifications to `.github/workflows/pages.yml`, `scripts/build_ion_forecast.py`, upstream SWIFT-TEC, ISEE calculations, or 365-day archive.

## Observation integrity
NICT official station names and WGS-84 positions:
- WAKKANAI/Sarobetsu (45.16 N, 141.75 E)
- KOKUBUNJI (35.71 N, 139.49 E)
- YAMAGAWA (31.20 N, 130.62 E)
- OKINAWA/Ogimi (26.68 N, 128.15 E)
Source: https://wdc.nict.go.jp/Ionosphere/en/conditions/04.html

NICT's official archive has 1-hour manual readings and 15-minute automatic readings, but an official stable JSON API suitable for direct GitHub Pages browser use was not confirmed. For this reason:
- Forecast curves **automatically** use the existing SWIFT-ION `docs/ion_forecast.json`.
- Observed curves appear only after importing actual foF2 observations in the CSV format below.
- The dashboard does not fabricate observations, pretend arbitrary user CSV was independently verified by NICT, or silently compare different UTC periods.
- Observation CSV is processed locally in your browser (not uploaded to an external server).

CSV schema (UTF-8):
```
station,time_utc,fof2_mhz,source
WAKKANAI,2026-11-21T00:00:00Z,,NICT_manual
```
The row above is an **example of format** with an empty observation cell, NOT an actual NICT observation.
Use station ids WAKKANAI, KOKUBUNJI, YAMAGAWA, OKINAWA; timestamps must be timezone-aware and values in MHz.
Missing values should be blank. Matching allows UTC ±15 min; do not compare observations from a different day as though they were contemporaneous.
Official source: https://wdc.nict.go.jp/Ionosphere/en/archive/

## Exports
- NICT dashboard → Excel: `Summary`, `Forecast_30min`, `Imported_NICT_Obs`, `Matched_15min`, `Sources_and_Notes`.
- Flight route Excel: `Route_100km`, `Flight_30min`, `Grid_100km_x_30min`, `Sources_and_Notes`.
- Both `.xlsx` exports use a local, standalone spreadsheet writer (`docs/shared/xlsx-lite.mjs`), so no Excel CDN or API key is required.
- `docs/field_customize.html` independently stores user color settings per metric in browser localStorage.

## Research limitation
foF2 is F2-layer critical frequency. It is not a predicted usable link frequency, MUF, mission-specific HF performance, or navigation availability. The IRI / TEC linked scenarios are experimental and not validated forecasts. I_P/I_N were not generated here; NICT-comparable I-scale requires 27-day and long-term local-time, seasonal and latitude-band reference statistics.
