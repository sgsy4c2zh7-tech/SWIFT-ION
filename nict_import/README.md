# NICT numerical import (not an API endpoint)

Place verified, numeric, UTF-8 CSV exports from the NICT four-site archive in this folder, e.g. `WAKKANAI.csv`, `KOKUBUNJI.csv`, `YAMAGAWA.csv`, `OKINAWA.csv`.

Required columns: `station,time_utc,fof2_mhz,source` with **UTC ISO 8601 and explicit Z / offset**, or `station,time_jst,fof2_mhz,source` with **JST local time and no offset**.
For single-site `WAKKANAI.csv`, `station` may be omitted. Example header only (NO invented observations):

    station,time_jst,fof2_mhz,source

NICT's native TEXT archive format is currently NOT verified. Transform official files before importing; never rename an HTML page to CSV or guess which numeric field is foF2. Check archive copyright/reuse and source attribution before publishing raw numerical data.

The automated repository workflow saves accepted readings in the `swift-ion-history` branch and publishes only a recent seven-day CSV. It uses them for future coefficient training ONLY if an older, actually issued forecast is available, with the preexisting chronological training gate.

Optional future HTTPS direct fetch: add an Actions secret `NICT_AUTO_SOURCE_URLS` containing JSON of four keys and independently verified official HTTPS **numeric CSV** download links. Do not set it to the HTML archive page. Unsupported native TXT is rejected, not guessed.
