# SWIFT-ION v0.9 — ionosonde validation and access conditions

## Source and access

- Public aggregation: https://prop.kc2g.com/api/stations.json (Andrew Rodland, KC2G)
- Underlying stations: GIRO and INGV ionosonde operators as applicable.
- Official GIRO rules: https://giro.uml.edu/didbase/RulesOfTheRoad.html
- GIRO station acknowledgements: https://giro.uml.edu/didbase/acknowledgements.htm
- Data from GIRO are released under CC BY-NC-SA 4.0, with additional Rules of the Road. **Use only for eligible non-commercial research**, credit GIRO, KC2G and each station's actual data provider, and check licensing before redistributing data or publishing analyses. A generic GIRO acknowledgement does NOT replace provider-specific acknowledgements.
- This dashboard and derived JSON are research outputs, not validated forecasts or operational products.

## Computation

- Fetch at most one public station feed per GitHub Actions run. No credentials or scrapers of authenticated portals.
- Filter out timestamps older than 6 hours, farther than 15 minutes into the future, non-finite/out-of-range measurements, and known confidence scores below 70. Records without CS are marked `confidence_known=false`.
- Deduplicate stations by name/coordinates, keeping the newest; choose up to 16 geographically separated stations.
- Run `iri2020.IRI()` independently **at each selected station's observation time and coordinates**. Do not pretend that a 4-day future SWIFT-TEC forecast was verified by a current station observation.
- Estimate foF2 from the maximum modeled F2-band Ne; modeled hmF2 is the sampled altitude at maximum Ne (25 km resolution) with boundary flag. Such hmF2 is only an F2-band proxy and must be distinguished from an ionogram hmF2 estimate.
- Compare model minus observation. Report `MAE`, `RMSE`, `Bias`, and sample count separately for foF2 and hmF2. Invalid/boundary model peaks are excluded from hmF2 statistics.
- If the feed cannot be retrieved, mark `SOURCE_UNAVAILABLE`; no fabricated values. If observations are stale, mark `NO_USABLE_OBSERVATIONS`.
- This is a model-to-station discrepancy at observation time, **not forecast accuracy**. To estimate forecast accuracy requires archived issue-time-controlled predictions and subsequent matching observations.

## Local commands

```bash
python -m unittest discover -s tests -v
python scripts/validate_ionosondes.py --max-stations 16 --max-age-hours 6 --min-confidence 70
```

Result: `docs/ionosonde_validation.json`; dashboard `docs/ionosonde.html`.

## Future scientific improvement

Acquire GIRO/DIDBase documented time-series access with permissions, preserve issued-at time for every archived prediction, add station-specific uncertainties and independent comparison datasets, then compute true lead-time-specific predictive skill. Prefer observing data with explicit manual-vs-autoscaled provenance when available.
