# Technical validation

`validate_extraction(folder, settings=Settings())` inspects extracted files read-only and returns `(report, report_path)`. Reports are created exclusively with UUID filenames under data/validation. No arrays, masks, calibration, background subtraction, downloads or extraction are produced. Technical validation determines structural capability, not scientific quality or readiness for all analyses.

## Checks

Required files: arrays.npz, tables.fits, metadata.json, report.json. IMAGE, VARIANCE and FLAGS must be nonempty 2D arrays with identical shapes; ZODI must match if present. Scientific arrays must be floating point and FLAGS integer. Dtypes and shapes must agree with extraction metadata. Nonfinite counts/fractions are recorded as warnings; they are not pixel rejection criteria. No masks are constructed.

Astropy Units requires IMAGE convertible to MJy/sr, VARIANCE convertible to its square, and ZODI compatible with IMAGE. FLAGS has no physical unit. Values and original units are never transformed. Original source BUNIT metadata is compared when available.

Provenance compares request/product/observation/collection across extraction metadata, extraction report where fields exist, downloaded manifest entry and manifest root. Source SHA-256 and size are checked if source exists. Missing source is a warning, not a false claim of verified integrity. OBSID and detector are checked against source headers and table detector headers. Extracted arrays and table values are compared with the source without re-extracting or saving new science data. Validation records hashes of the four extraction files for subsequent reproducibility; these are current hashes, not pre-existing signed baselines. Unknown optional identity fields are distinguished from explicit mismatches. Product/request identity is required. No identity is guessed from a filename.

## WCS

Astropy's full all_pix2world/all_world2pix path honors SIP. The default 5x5 grid includes all four corners and interior points; the center is explicitly included. Pixels use (x=column,y=row), origin=0, while arrays use (row,column). World values must be finite with RA in [0,360) and Dec in [-90,90]. Default maximum Euclidean roundtrip error is 0.001 pixel; configure roundtrip_tolerance_px and grid_size in Settings. SIP inversion allows up to 100 iterations. Serialized and source celestial WCS are also compared at center/corners using wrapped RA differences. This checks computational consistency and retention, not absolute astrometric accuracy; no new astrometric fit is made.

## Spectral and EPSF

WCS-WAVE must be a readable one-row binary table with X,Y,VALUES, increasing finite control grids, and VALUES shape (len(Y),len(X),2). Table schema, TDIM, units and extracted metadata must agree. Units not declared in the original are retained as unknown; they are not invented. EPSF checks the eleven columns present in this product family, integer bin/count fields, finite numeric values and a nonempty 3D stack of 2D EPSFs. It does not assume 441 regions, 21x21 binning or a fixed kernel size. Detector headers must agree. No PSF fitting occurs.

Capabilities are independent: spatial_wcs_available, spectral_table_valid, spectral_maps_available and epsf_available. No wavelength/bandwidth maps are generated or validated; spectral_maps_available remains false. A valid table with missing derived maps is a warning and does not automatically reject spatial data. Precise spectral analysis needs the appropriate CWAVE/CBAND calibration; WCS-WAVE visualization metadata alone does not establish precision.

## Status and limits

Critical structure, missing required data, invalid units/WCS and provenance/integrity mismatch cause failed. Incomplete optional metadata, nonfinite pixels and absent derived spectral maps cause warnings. All essential checks passing gives passed or passed_with_warnings. eligible_for_scientific_quality_validation is true only without errors. This authorizes the next quality assessment, not scientific use.

Settings limits each input file and expanded NPZ members to 512 MiB by default. This is in-memory validation for bounded extracts, not an untrusted-file sandbox. Missing/unreadable data produces structured error reports; report-storage failures propagate. The spectral and EPSF schema checks target the actual current SPHEREx product family and may need an explicit versioned adapter for future layouts.

## Usage and tests

```python
from technical_validation import validate_extraction, Settings
report, path = validate_extraction(
 'data/extractions/1ff9732e-6d34-47fe-a479-ce385ceeef35',
 settings=Settings(roundtrip_tolerance_px=0.001))
```

Run `python -m pytest -p no:cacheprovider tests` from Data_Preparation_Pipeline. Unit, integration and scientific tests cover valid/bad arrays, missing data, nonfinite reporting, units, SIP, wraparound, poles, nonsquare pixel ordering, tables, identity and hash mismatch, missing source warnings and persisted reports. Real M101 integration uses the existing extraction and source, without network or a new download. The full regression suite passed 139 tests.

Reference: https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/ (original units, astrometric/spectral WCS, EPSF and WCS-WAVE layouts). Technical acceptance does not replace Scientific Quality Validation.
