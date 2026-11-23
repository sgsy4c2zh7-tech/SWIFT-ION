#!/usr/bin/env python3
"""Idempotent, minimal patch to the current SWIFT-ION .github/workflows/pages.yml.
Run from repository root. Existing forecast/validation/history stages are preserved.
"""
from pathlib import Path
import sys
p=Path('.github/workflows/pages.yml')
if not p.is_file(): sys.exit('ERROR: Run this in SWIFT-ION repository root.')
s=p.read_text(encoding='utf-8')
marker='      - name: Prepare GNSS current TLE snapshot (latest only)\n'
anchor='      - name: Calculate SWIFT-TEC VTEC forecast and 30-minute animation\n'
step = """      - name: Prepare GNSS current TLE snapshot (latest only)
        run: |
          python scripts/build_gnss_latest.py
          test -s docs/gnss_latest.json
          test -s docs/vendor/satellite.min.js
          python -c "import json; p=json.load(open('docs/gnss_latest.json')); assert p['is_latest_only'] and len(p['satellites']) > 0"

"""
if marker in s:
 start=s.index(marker)
 end=s.find('      - name: ',start+len(marker))
 if end<0:sys.exit('ERROR: Cannot find end of previous GNSS step')
 s=s[:start]+step+s[end:]
else:
 if s.count(anchor)!=1 or '      - name: Read upstream SWIFT-TEC (read-only)\n' not in s:
  sys.exit('ERROR: Unexpected workflow structure, refusing to modify')
 s=s.replace(anchor,step+anchor,1)
p.write_text(s,encoding='utf-8')
print('GNSS latest-only creation + validation step configured; existing workflow preserved.')
