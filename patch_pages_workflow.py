#!/usr/bin/env python3
"""Apply only one idempotent addition to the existing SWIFT-ION pages workflow.
Run from the repository root after copying files from the ZIP.
Leaves all other workflow lines unchanged; errors if structure has changed.
"""
from pathlib import Path
import sys

workflow = Path('.github/workflows/pages.yml')
if not workflow.exists():
    sys.exit('ERROR: Run from the root of the SWIFT-ION repository (.github/workflows/pages.yml must exist).')
s = workflow.read_text(encoding='utf-8')
addition = ('      - name: Prepare GNSS current TLE snapshot (latest only)\n'
            '        run: python scripts/build_gnss_latest.py\n\n')
if 'name: Prepare GNSS current TLE snapshot (latest only)' in s:
    print('No changes necessary. GNSS latest-only workflow step already exists.')
else:
    anchor = '      - name: Calculate SWIFT-TEC VTEC forecast and 30-minute animation\n'
    if s.count(anchor) != 1 or '      - name: Read upstream SWIFT-TEC (read-only)\n' not in s:
        sys.exit('ERROR: Existing Pages workflow is different. No changes written. Insert the step manually after the SWIFT-TEC clone step.')
    s = s.replace(anchor, addition + anchor, 1)
    workflow.write_text(s, encoding='utf-8')
    print('Updated .github/workflows/pages.yml (added only the GNSS latest snapshot step).')
