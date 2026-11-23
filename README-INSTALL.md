# SWIFT-ION v2.4 — foF2 ±2 MHz primary skill / Kp activity diagnostics

## Installation (GitHub Desktop)

This is a **complete v2.3 → v2.4 integration patch**, designed to apply onto the current SWIFT-ION repository even if you have not yet installed v2.3. Unzip at the SWIFT-ION repository ROOT, merging/overwriting these folders:

- `.github/workflows/pages.yml`
- `scripts/`
- `docs/`
- `tests/`

Do NOT replace the entire existing folders with only the patch folders (merge files). Keep other repository files untouched.

Suggested GitHub Desktop Summary:

`Set TEC-linked foF2 primary hit rate to ±2 MHz and add Kp diagnostics`

Commit to `main` → Push origin. Check GitHub Actions **Run unit tests** and workflow deployment. Then open `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/year.html`.

## Accuracy model

- Main indicator: issued **final TEC-linked foF2**, strict `STANDARD` quality, same-run verified NOAA 3-day Kp provenance, observations acquired **after** the forecast issue, **±2 MHz**.
- Also: simultaneous independent tolerance rates **±1** and **±3 MHz** with the **same denominator**.
- MAE, RMSE, signed Bias (predicted − observed), mean absolute percentage error (MAPE), same-observation IRI-versus-TEC MAE improvement (positive means improvement).
- Forecast Kp group diagnostics: quiet (`Kp<4`), active (`4<=Kp<5`), storm-equivalent (`Kp>=5`) and unknown. These refer to **forecast Kp**, not proof that a geomagnetic storm was observed.
- Stage-by-stage accuracy: physics / empirically calibrated / nonlinear ML. Their acceptance and training continue to rely on chronological held-out **MAE**, not the new hit threshold.
- The historic standalone IRI climatology reference (old separate source) is **unchanged**, including its legacy ±1 MHz definition. Don't compare its displayed aggregate with TEC main without matched samples.
- NICT 4-station supplementary reports also show ±2 main, ±1/±3 alternatives, RMSE. **Automated direct acquisition from NICT's official numeric archive remains conditional on verified URL/CSV import.** No observations are fabricated and the AI will not become active without sufficient measured matches.
- Low-confidence `EXTENDED` cases never silently enter strict headline skill or model training; empty samples show "awaiting evaluation" rather than a fake 0%.

## Included files

- Full v2.3 necessary integration files (Pages workflow, SWIFT-TEC/Kp provenance, main model and history) 
- New v2.4 files `scripts/build_tec_skill.py`, `scripts/build_fof2_stage_skill.py`, `scripts/build_nict_fof2.py`, `docs/year.html`, `docs/nict_skill.html` and `tests/test_v24_threshold_skill.py`.

## Verification

- 57 localized Python unit tests passed (existing v2.3 subset + 7 new v2.4 tests).
- JavaScript syntax validation passed for updated HTML scripts.
- Headless Chromium smoke test: ±2 headline, ±1/±3 rates, MAE/RMSE/MAPE, IRI improvement, Kp cohort rows, and missing 72h period with "awaiting evaluation". Actual deployed model performance and GitHub Actions end-to-end must be checked after Push.
