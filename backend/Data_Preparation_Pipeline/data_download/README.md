# Data Download

Downloads explicitly selected products from Search Catalog schema 1.0. `load_catalog` reads JSON; `download_batch(catalog, report, request, acceptance, selected_ids)` checks matching search and accepted request IDs, documented search status, product identity, downloadable=true and an original HTTPS URL from irsa.ipac.caltech.edu. A partial catalog can supply explicitly selected products, with a warning; it is never treated as complete. Ambiguous publisher IDs with multiple catalog matches require an unambiguous selection catalog. No implicit 386-product download occurs.

## Modes and geometry

Default mode `cutout` is enabled only for `/ibe/data/spherex/*.fits` URLs without existing queries. It uses documented IBE parameters `center=RA,Decdeg`, `size=FOVdeg`, `gzip=false`. IRSA preserves its MEF extensions. FOV is the angular diameter of the requested circular search region; IBE returns an image-axis-aligned rectangular cutout with that angular size, not a circular pixel mask. Cutouts may be clipped to the available image. This stage neither extracts extensions nor performs WCS mapping. Explicit `mode='full'` preserves the original access URL and stores the full file; no automatic full-file fallback exists.

## Resources and storage

Sequential downloads use requests streaming in 64 KiB chunks. Limits defaults: one product, 128 MiB per file, 256 MiB network-byte budget across attempts, 10-second connect timeout, 60-second read timeout, one retry with exponential backoff. Retry applies to connection failures, timeouts, interrupted transfer and HTTP 408/429/5xx. Limits are configurable. Rejected length headers can avoid transfer; streamed bytes are still checked. The budget can observe one chunk beyond a limit before stopping; that chunk is not written. `cancelled` is a callback checked between chunks; it cannot interrupt a currently blocked read until the read timeout. Remaining requested products receive their own failure entries. Redirects are rejected, preventing a redirect from escaping the trusted origin.

UUID file names never use archive paths. Temporary `.part` files are created exclusively inside data/cutouts or data/raw. After transport and smoke validation, atomic hard-link publication refuses an existing destination. Temporary files are cleaned on failure. This requires a filesystem supporting hard links (the project Windows filesystem passed the test). Manifests are reserved exclusively in data/manifests and updated atomically, with bounded retry for transient Windows locks. Storage or manifest write errors propagate; a caller must not report batch completion in that case.

## Integrity and reproducibility

HTTP status, source URL, parameters, request/product/observation IDs, collection, processing version (null if absent), metadata, file size, SHA-256, UTC completion time and result/error are retained. New manifests include request, acceptance and search-report snapshots. Content-Length is checked when present. `access_estsize` is approximate and is not used as an exact byte count. Full downloads compare exact raw contentlength and sha256 contentchecksum if supplied. Current SIA catalog has neither; cutout checksums cannot be compared to checksums for the parent image. No checksum is invented.

Primary FITS signature, block alignment, header verification and HDU data spans are checked with Astropy without extracting science arrays. This rejects HTML, malformed bodies and truncated data, but does not establish scientific validity or deep technical quality. Successful entries list extension names. Future fits_extraction can consume downloaded manifest entries and local paths; it is not invoked here.

## Usage and tests

From Data_Preparation_Pipeline:

```python
from data_download import load_catalog, download_batch
catalog = load_catalog('data/search_results/<run>/catalog.json')
# report, request and acceptance must describe the same accepted search.
entries, manifest = download_batch(catalog, report, request, acceptance,
    [catalog['products'][0]['product_id']])
```

Run `python -m pytest -p no:cacheprovider tests`. Tests use tiny synthetic FITS and mocked HTTP. `python -m data_download.live_verify` performs a bounded live test, tries at most two products only if the first fails, and never falls back to full files.

## Live evidence and limits

The existing M101 catalog was read successfully (386 products). First product `ivo://irsa.ipac/spherex_dr1?2025W19_2B_0101_1/D3` downloaded successfully on the first attempt, 4083840 bytes, SHA-256 f510a56ec8ae98a1587c6ca8a5711c4f09b052eef7bcddf7f2f2b4e8b9ca93a9. Astropy opened PRIMARY, IMAGE, FLAGS, VARIANCE, ZODI, EPSF and WCS-WAVE. Manifest 22bc3053-7cf8-4786-b187-692a0bf5f218.json was reread and compared with the file size and a recomputed hash. Earlier search did not persist its original normalized request; the live verification reconstructs the recorded M101 geometry from the saved POS, retains the original report request_id and obtains a fresh validation report. It does not claim the original request file existed. No previous pipeline code was modified.

Sources: https://irsa.ipac.caltech.edu/ibe/cutouts.html (SPHEREx support, angular units, MEF preservation, clipping); https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts/ (official spectral image example).
