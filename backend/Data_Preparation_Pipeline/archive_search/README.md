# Archive Search: SIA2 primary, TAP secondary

The public `archive_search.search(request, acceptance)` now uses IRSA SIA2. Use `service='TAP'` explicitly for the preserved TAP/ADQL implementation. There is no automatic TAP fallback and no automatic catalog merge. The existing TAP, async, diagnostics, schema snapshot and retrieval utilities remain available.

## Input and usage

Pass the original normalized request and its matching accepted Request Validation report. The report must have the same request_id, status accepted, and no errors. No name resolution or validation stage is rerun. Example, from Data_Preparation_Pipeline:

```python
from user_input import create_request
from request_validation import validate_request
from archive_search import search, save_results, SIASettings
request = create_request('coordinates', {'ra': 210.80227, 'dec': 54.34895}, 'sky_viewer')
acceptance, original = validate_request(request)
catalog, report = search(original, acceptance, settings=SIASettings(maxrec=10000))
folder = save_results(catalog, report)
```

## Collections and spatial search

Default collections: spherex_dr1, spherex_dr1_deep, spherex_qr3, spherex_qr3_deep. Cubes and QR1/QR2 are excluded. Exact collection metadata maps to release and wide/deep; detector maps only explicit SPHEREx-D1..D6. Search sends POS=CIRCLE in ICRS decimal degrees with radius=fov_deg/2, DPTYPE=image, CALIB=2 and FORMAT=image/fits. Response classification is checked again.

IRSA documents POS as intersection of the requested shape and image footprint, including edge-only overlap. This differs from center containment. The implementation delegates spherical geometry, RA wraparound and polar handling to SIA2; it does not implement a second geometry engine. IRSA approximates image boundaries with great-circle polygons. Returned overlap is not proof of full coverage or scientifically valid pixels. Scientific tests check argument preservation and absence of local center filtering; they do not independently certify the remote geometry engine.

## Limits and completeness

SIASettings controls MAXREC (10000 per collection), timeout (45 seconds per attempt), response bytes (32 MiB), retries (one, bounded backoff). Requests streams metadata; Astropy decodes VOTable with official FIELD names rather than generated IDs. QUERY_STATUS must exist and be OK or OVERFLOW. Empty/malformed/error responses fail. OVERFLOW, a reached record cap, byte/time limits or any failed collection prevent completed status. Complete means all requested collections returned valid OK replies under the limits. It is a snapshot of the SIA index, not proof that future ingestion cannot add products. No pagination is assumed. No partitioning is enabled. Overflow is reported partial; callers can retry with a larger bounded cap. SIA ingestion can lag other IRSA access channels.

Status: completed (complete replies, products), no_results (complete replies, none), partial (some valid replies, missing/truncated retrieval), failed (all collection queries failed). Reports include parameters, region, service, per-collection status/count/units, timestamps, errors and raw-row/unique counts.

## Catalog and eligibility

Catalog schema_version 1.0 contains products and raw_rows. Product records retain publisher product ID, observation ID, collection(s), release, survey, detector, data type, calibration level, original access URL/format, footprint, MJD bounds, meter wavelength bounds, processing version when supplied, source service and raw metadata. Unknown values remain null. No processing version is guessed from filenames. Duplicate key is (publisher ID, original access URL, explicit processing version), preserving different observations, detectors and processing access variants. Matching products found in multiple collections retain the collection list. Missing identity is never silently deduplicated.

Download eligibility requires an original publisher ID, matching known collection, L2 image metadata, FITS MIME type and HTTPS URL at irsa.ipac.caltech.edu. This is permission to attempt a later download, not FITS integrity or scientific quality validation. No product URL is fetched here. save_results writes catalog.json and report.json into a newly created UUID directory under data/search_results, preventing overwrite.

## Tests and live evidence

Run `python -m pytest -p no:cacheprovider tests` from the pipeline directory. `python -m archive_search.live_sia` performs the bounded live/end-to-end checks. Live and mocked results are distinct. The M101 live run saved under data/search_results/d6f57c3e-f6aa-488e-95a7-ac6f1072dd73 returned 254 DR1, 132 QR3, zero deep at that location, with OK replies and no OVERFLOW. All 386 products had eligible metadata. Deep tests use a J2000 north ecliptic pole transformed by Astropy, based on the Explanatory Supplement; southern pole coordinates are not invented.

## Sources and remaining limits

https://irsa.ipac.caltech.edu/ibe/sia.html (POS, CALIB, DPTYPE, MAXREC, TIME and service limits)
https://irsa.ipac.caltech.edu/spherex-archive-documentation/spherex-data-access/ (collections)
https://www.ivoa.net/Documents/SIA/20151223/REC-SIA-2.0-20151223.pdf (SIA2 specification; direct documentation fetch unavailable during implementation)
https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf (north deep field)
https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts/ (spectral image products and SIA ingestion delay)

TAP remains bounded and experimental: earlier center queries timed out; circle-first INTERSECTS returned BAD_REQUEST. TAP geometry, classification and complete retrieval are not verified. SIA2 returns a service-defined approximate footprint and an index snapshot. No guaranteed partitioned retrieval is implemented for overflowing queries. Catalog eligibility does not inspect FITS extensions or file contents.

Deep live evidence: data/search_results/72594c9b-aa68-4b0b-ae51-cc3c6420fde5 contains 100 DR1 Deep and 100 QR3 Deep rows at the transformed north ecliptic pole. Both replies reported OVERFLOW; status is partial, not complete. The combined deep catalog contains 200 unique access variants. Final local regression run: 79 passed, 0 failed, 0 skipped, including SIA timeout retry and byte-limit checks. The saved M101 catalog was independently read back and all 386 products had the required metadata for a later download attempt.
