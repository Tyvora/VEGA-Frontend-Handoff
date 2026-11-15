# Algorithm Inputs

Stage nine packages the existing M101 extraction and masks according to Analysis Readiness. It does not rerun extraction/validation/readiness, execute algorithms, create measurements, download data or generate VEGA-AI payloads. The source stages and shared contracts remain unchanged.

## API and package structure

```python
from algorithm_inputs import prepare_packages, load_package
report, report_path = prepare_packages(
 'data/readiness/2e841b5e-f60b-489a-9e2b-81840a4befda/readiness_report.json')
package = load_package(report['packages']['sky_visualization']['path'])
print(package.metadata['capability'], package.decision['status'])
print({name: (array.shape, str(array.dtype)) for name, array in package.arrays.items()})
```

Each run is data/algorithm_inputs/<UUID> with preparation_report.json and only allowed capability directories. Each package contains arrays.npz, metadata.json, readiness.json (the full unchanged readiness snapshot), manifest.json and COMPLETE. Every package has its own UUID metadata identity; raw product IDs never become filenames. No empty files are required. Blocked capabilities are recorded in preparation_report.json without creating package directories.

A .staging-UUID run is built and each package is reread before the run is atomically renamed to its published UUID. Failed stages are retained only as diagnostics and are not published. Consumers should discover runs through completed preparation reports, not scan .staging folders. COMPLETE stores the manifest SHA-256; it is written after package files and manifest. Save/serialization/readback failures raise instead of returning success. Existing runs are never overwritten.

## Data contract

package_schema.json is a local JSON Schema 2020-12 for metadata, with schema_version=1.0 and preparation_version=vega-packaging-1.0. It requires identity, references, original shape/dtypes, units, ICRS, WCS, timing/spectral metadata and the exact readiness decision. Unknown root metadata fields are rejected. NPZ has actual structural checks beyond JSON Schema.

Arrays: IMAGE, VARIANCE, FLAGS, optional ZODI, analysis_mask, background_mask. All remain 2D and preserve shape and scientific dtypes/endianness. IMAGE/VARIANCE/ZODI remain floating point, FLAGS integer, masks boolean. background_mask must remain a subset of analysis_mask. Array specs and units are compared to original extraction metadata; masks retain their True meanings from quality validation. Only these approved array names are accepted; no fake wavelength maps can be added implicitly. Units are retained without converting IMAGE to Jy or VARIANCE to sigma.

Celestial WCS header is preserved exactly. Array order is (row,column); WCS pixel order is (x=column,y=row), origin=0. Observation DATE/MJD fields and TIMESYS are copied from extraction observation metadata, not inferred. Detector/collection/processing version and source SHA-256 are retained; unknown values stay null. Spectral metadata retains the original limitations and technical capability flags.

EPSF and WCS-WAVE are referenced in the existing tables.fits with a bound SHA-256 rather than copied. `with package.open_tables() as tables:` gives local read-only access after integrity verification. These packages are reference-dependent: moving/deleting/changing prior source files invalidates the reader. They are offline-readable in the project but are not portable standalone archives.

## Readiness enforcement

The only supported readiness policy adapter is vega-readiness-1.0. All readiness evidence hashes are checked before creation and before publication; metadata/request/product/observation identities and stage references must match. The entire original report is retained. No capability is promoted or reassessed.

- ready + allow_preparation permits the specifically scoped package.
- conditional + allow_preparation permits preliminary packaging only, retaining limitations and allow_scientific_execution=false. Source detection and photometry remain conditional on M101.
- blocked or allow_preparation=false produces no package.
- Contradictory conditional/blocked scientific gates, unknown states or mismatched policy versions are rejected.

`package.authorize_execution()` reopens and revalidates the on-disk package and its decision. It returns a scoped permission record only for ready with explicit allow_scientific_execution=true; it never calls an algorithm. Conditional packages raise PermissionError. For photometry, `authorize_execution('calibrated_flux')` also honors the nested method gate, so the parent preliminary package cannot authorize calibrated measurements. Mutating in-memory metadata cannot grant permission. Raw diagnostic reading is allowed, and this API is not a sandbox preventing unrelated code from reading local NPZ files.

Visualization permission covers spatial display only. It is not permission for validated detection, photometry or other scientific results. Background/temporal/spectral are currently blocked and have no execution package. Future supported multi-observation/science-spectral packaging needs an explicit new layout/adapter; the full readiness report retains multiple evidence records, but this version refuses to create a fabricated paired/spectral layout if those capabilities later become permitted.

## Integrity and reader

Manifest lists hashes, sizes, content types and provenance for created arrays/metadata/readiness files and hashes of external references. COMPLETE binds the manifest without an impossible self-hash cycle. Reader verifies all package and external hashes, schema, identity, exact readiness snapshot/decision, references, original units/WCS/specs and NPZ shape/dtype. Expanded NPZ memory defaults to 512 MiB. Returned arrays are read-only. Original FITS is required and checked against its source SHA-256.

These are local integrity/provenance hashes, not digital signatures. An attacker who can rewrite all referenced sources and recompute all hashes is outside this integrity model. The prior quality-mask authorship limitation remains in the preserved readiness warning; packaging does not manufacture missing historical evidence.

## Real M101

Published run: data/algorithm_inputs/c40a0dfa-5780-48d5-bea2-ff235c0274c2. It has sky_visualization (ready), source_detection (conditional) and photometry (conditional). Background estimation, temporal comparison and spectral analysis are recorded as unavailable. Arrays are all (59,58): IMAGE/VARIANCE/ZODI >f4, FLAGS >i4, masks bool. Original units are MJy / sr and MJy2 / sr2. EPSF and WCS-WAVE remain referenced, spectral maps remain unavailable. Masks and science arrays were compared with original files and the reader checked hashes. No algorithms ran.

Independent CLI (does not call the creator):

```text
python -m algorithm_inputs.inspect_package data/algorithm_inputs/c40a0dfa-5780-48d5-bea2-ff235c0274c2/sky_visualization
```

Run `python -m pytest -p no:cacheprovider tests`. Tests cover creation/readback, exact real arrays/masks/WCS, hashes and corruption, schema/units, missing arrays/references, shape/dtype errors, conditional and nested-method authorization, blocked package absence, identity/gate conflict, source immutability and unpublished save failures. The reader can be used without any IRSA connection.

## Remaining science requirements

The 20 background candidates are not an approved background estimate. No pixel solid-angle map or calibrated photometry method has been supplied. One prepared observation cannot support temporal comparison. WCS-WAVE is not a substitute for science-grade CWAVE/CBAND calibration. Adding a future algorithm requires a new explicit layout/contract and a new accepted readiness report with the appropriate scoped permissions, never an override flag here.
