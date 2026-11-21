# SWIFT-ION v1.1 — 365-day forecast & hit-rate history

## Purpose

Adds long-lived **rolling 365-day** retention of ionosonde station outlooks, verified
observations and matched predictions to branch `swift-ion-history`. Uses UTC and
keeps issue time, valid time, station, confidence, model and lead. A separate
Git branch avoids modifying SWIFT-TEC and prevents adding binary/large archive
files to `main`/GitHub Pages. Initial deployment does **not** invent old forecasts.

### Hit-rate definitions (configurable scientific thresholds)
- foF2 hit: `abs(forecast_fof2 - ionosonde_fof2) <= 1 MHz`.
- hmF2 hit: `abs(forecast_hmf2 - ionosonde_hmf2) <= 30 km`.
- Each metric has separate denominator and is `null` when no valid pairs.
- Also saves MAE, RMSE, bias and sample sizes by UTC day/month and nominal
  lead 1/3/6/12/24 hours. They are **IRI climatology baseline** estimates,
  not SWIFT-TEC-corrected ionosphere forecasts or validated operational skill.

## Installation (GitHub Desktop)

1. Extract this ZIP to a temporary folder.
2. Merge `.github`, `scripts`, `tests`, `docs` into your **SWIFT-ION repo root**.
   Overwrite `.github/workflows/pages.yml`; DO NOT replace SWIFT-TEC itself.
3. In GitHub Desktop commit: `Add rolling 365-day IRI forecast and accuracy history`.
4. Push origin. On GitHub, check **Settings > Actions > General > Workflow permissions**.
   The workflow needs **Read and write permissions** so it can write the separate
   `swift-ion-history` branch; the workflow explicitly requests `contents: write`.
5. Check Actions: `Prepare rolling-year archive branch`, `Record prospective...`,
   `Commit 365-day history...`, and `Deploy GitHub Pages`.
6. Open `https://sgsy4c2zh7-tech.github.io/SWIFT-ION/year.html`.
   Latest short-term view: `.../skill.html`.

## How persistence works

- The archive branch has gzipped daily JSONL for `outlooks/`, `observations/`,
  and `matches/`, plus a README. Only the **active files** from the most recent
  365 days are retained. Earlier versions could still exist in Git history;
  removal from all commit history would require a separate purge operation.
- History is reloaded each scheduled run, checked for duplicates and compared
  to the latest released KC2G/GIRO-derived observations. A newly produced
  forecast cannot be scored immediately against observations from the future.
- GitHub Actions snapshots may still expire in 7 days; **the Git branch is the
  actual 365-day retention store**. Branch protection or disabled workflow
  permissions can prevent writes; monitor the `Commit` step.
- `docs/year_accuracy.json`, `docs/year_daily.csv`, `docs/year_monthly.csv`
  are rebuilt for the website. The branch remains separate from Pages.
- Data availability, nominal/actual lead mismatch, sampling gaps, and future
  corrections must be communicated when interpreting a hit rate.
- Use is noncommercial research only. GIRO/INGV/KC2G attribution/permission
  obligations still apply for stored/public evaluation data.

## Test locally

Within the existing SWIFT-ION repository:

```
python -m unittest discover -s tests -v
```

New scripts are pure Python 3.11 stdlib, but the IRI-2020 runtime is required
when actually running future outlook issuance. Passing local offline tests
**does not** prove successful 365-day storage on GitHub Actions.
