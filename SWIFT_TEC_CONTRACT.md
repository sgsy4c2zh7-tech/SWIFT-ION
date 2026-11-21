# Proposed SWIFT-TEC public export contract

**Proposed contract only — not verified against existing SWIFT-TEC implementation.**

`data/input/swift_tec.json` example:

```json
{
  "schema_version": "swift-ion-tec-v1",
  "source": "SWIFT-TEC",
  "issued_at": "2026-11-21T00:00:00Z",
  "valid_at": "2026-11-21T00:30:00Z",
  "model_version": "example-only",
  "correction_stage": "post_ml",
  "cells": [{"lat": 35.0, "lon": 140.0, "vtec_tecu": 18.0}]
}
```

All timestamps must be UTC ISO 8601 with offset. TEC in TECU (1 TECU = 10^16 electrons/m^2). Cells are VTEC, not slant TEC. The original producer, version, correction stage, issue time, validity time and grid metadata must be preserved. Do not create a forecast from an observation without clearly marking it. Validate exact source file paths and schemas before automating sync. The SWIFT-TEC repository must remain unchanged.
