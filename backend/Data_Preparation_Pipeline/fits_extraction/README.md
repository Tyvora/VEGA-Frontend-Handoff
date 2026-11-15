# FITS extraction

`extract(manifest_path, product_id)` reads exactly one downloaded entry and writes a new UUID directory under `data/extractions`. It verifies the source path lies in pipeline raw/cutouts, the file size and SHA-256 match the manifest, and the request identity agrees. Observation ID and detector are compared with IMAGE headers when both sources provide them. Product/collection linkage comes from the hash-bound download entry; no independent product ID is invented from a filename. Original FITS is opened read-only and its hash is rechecked at completion.

## Outputs

- arrays.npz: IMAGE, VARIANCE, FLAGS, ZODI when present. Numpy preserves dtype, endianness, shape and values including NaN. No variance square root, background subtraction, flag interpretation or mask creation occurs. Load with `np.load(path, allow_pickle=False)`.
- tables.fits: copies of original PRIMARY and available EPSF/WCS-WAVE HDUs, including column types, TDIM, TUNIT, headers and table data. This preserves multidimensional FITS columns rather than lossy JSON conversion. No EPSF averaging or fixed-PSF assumption is made.
- metadata.json: schema version, source/manifest provenance, original header card strings (including duplicate HISTORY and comments), extension name-to-index mapping, units, table schema, observation header fields, processing version from PRIMARY VERSION and celestial WCS.
- report.json: completed/partial/failed, extracted/missing extensions, warnings, errors and readback verification. Missing or empty extensions give partial; invalid types, identity/integrity conflicts, resource and I/O errors give failed. Consumers must inspect this report; files in failed directories must not be treated as valid outputs. If even the report cannot be saved, the I/O error propagates.

## Celestial WCS and cutouts

Astropy WCS reads the actual IMAGE header with its projection and SIP distortion. The original header and a serialized celestial WCS are retained, along with CRPIX (FITS 1-based), CRVAL, array shape and reference-plane pixel scales. The latter are local reference scales, not a global linear approximation. Sample zero-based pixel-to-world transforms use Astropy's full WCS. Negative or outside-array CRPIX is retained: a cutout need not include the reference pixel. No reprojection or alignment occurs.

## Spectral WCS and EPSF

WCS-WAVE and EPSF remain full FITS tables associated with their original detector headers. Derived per-pixel WAVELENGTH/BANDWIDTH arrays are intentionally unavailable: cutout-to-parent offsets and the calibration reconstruction have not been independently verified for this file. The report states this restriction explicitly. No wavelengths are guessed. Table units absent in the FITS remain null; no units are invented for WCS-WAVE X/Y/VALUES columns.

## Limits and API

```python
from fits_extraction import extract, ExtractionLimits
report, folder = extract(
 'data/manifests/22bc3053-7cf8-4786-b187-692a0bf5f218.json',
 'ivo://irsa.ipac/spherex_dr1?2025W19_2B_0101_1/D3')
```

Defaults are 256 MiB source bytes and 512 MiB total array bytes. Image dimensions are checked before materialization; table/expanded data sizes are checked after decoding. This is bounded small-file extraction, not a streaming extractor for arbitrary large/compressed/variable-length tables. Outputs never replace source files or previous UUID runs. Saving each stage is not a multi-file transaction; failed output directories are retained for diagnosis and explicitly marked failed. This stage does not grant technical or scientific validity.

## Real M101 verification

Actual HDUs: PRIMARY, IMAGE, FLAGS, VARIANCE, ZODI, EPSF, WCS-WAVE. IMAGE/VARIANCE/ZODI are big-endian float32, shape (59,58); FLAGS is big-endian int32 with unchanged bits and an empty BUNIT. Units: IMAGE/ZODI MJy / sr; VARIANCE MJy2 / sr2. EPSF has 451 rows and eleven columns, including a 33x33 float64 EPSF field; it is not assumed to always have 441 rows. WCS-WAVE has one row, X[9], Y[14], VALUES[14,9,2]. Celestial frame ICRS, TAN-SIP; PRIMARY VERSION=7.0.5; IMAGE DETECTOR=3; observation timing is UTC in DATE/MJD fields. Arrays and every retained table column were reloaded and compared with the source. The source hash remained unchanged.

First verified output: data/extractions/1ff9732e-6d34-47fe-a479-ce385ceeef35. Other integration runs create their own UUID directories. Run `python -m pytest -p no:cacheprovider tests` from the pipeline directory. Tests cover real and synthetic FITS, flags, shapes/dtypes, units, tables, missing/empty/wrong-type HDUs, WCS reference coordinates, resource limits, identity mismatch, invalid FITS and saving failure. No network is used.

References: https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/ ; https://irsa.ipac.caltech.edu/spherex-archive-documentation/spherex-data-products/ (direct page unavailable during this run); https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf .
