# Analysis Readiness

Stage eight evaluates method-specific prerequisites and execution gates; it never runs science algorithms or writes Algorithm Inputs. It reads the existing extraction, technical and quality formats through an evidence adapter rather than rerunning those stages. Shared data_contract.json and output_contract.json remain empty as originally supplied; this module does not assign them an invented meaning. readiness_report.json declares its own schema_version=1.0.

## API

```python
from analysis_readiness import evaluate_readiness, InputReferences, Policy
report, path = evaluate_readiness([InputReferences(
 'data/extractions/1ff9732e-6d34-47fe-a479-ce385ceeef35',
 'data/validation/technical-a34702f2-8963-4afe-8bb1-6d48ac6c75b6.json',
 'data/quality/7cf8cf36-233b-48ab-9afa-789050bbb3ab')])
```

Additional genuinely prepared observations can be passed as further InputReferences. No Search Catalog product is counted as prepared. Duplicate product references are rejected; distinct product IDs alone do not establish independent exposures.

## Evidence checks

Metadata, extraction report, technical report, quality report and metrics are loaded from the supplied references. Technical and quality failures block all trusted decisions. Request/product identities must be known and match; observation identities must agree when available. Absolute extraction/technical references must match. The current adapter supports quality policy vega-dr1-qr3-conservative-1.0 only. Unknown policies are rejected, never treated as accepted by default.

All four extracted file hashes must match the technical report. Masks must be readable boolean arrays of IMAGE shape, agree with quality mask metadata, reason arrays and reported counts/fractions, and background must be a subset of analysis. Mask-selected image and variance values receive consistency checks; flag definitions are not reinterpreted and masks are not regenerated. Input file hashes are recorded and rechecked for changes during evaluation. Expanded NPZ limits are 512 MiB for arrays and 128 MiB for masks.

The previous Quality producer did not save independent hashes for its output files. Consequently this stage proves reference/identity/policy and internal consistency, and records current hashes; it cannot independently authenticate who generated a mask or detect every coordinated alteration of masks, reasons and reports. This limitation is explicitly carried as a warning, without modifying the previous stage. Reports are local provenance records, not signed attestations.

## Policy vega-readiness-1.0

ready: mandatory requirements for the specifically scoped capability are evidenced. conditional: limited preparation is allowed, but scientific execution requires the stated conditions and a qualified method. blocked: a mandatory prerequisite is missing/invalid. Every capability has status, stable reason_codes, evidence, missing_requirements, warnings, required_next_steps, policy_version, allow_preparation, allow_scientific_execution and execution_conditions.

- Sky visualization: image, units, verified celestial WCS and usable pixels are required. Spectral maps are not required. A ready display gate permits spatial visualization only; it does not authorize detection, photometry or validated science claims.
- Source detection: image, variance, noise information, analysis mask support and celestial WCS are required for the declared sky-coordinate detection scope. Spatial distribution is recorded. No detection method or independent background estimator has been qualified, so valid basic inputs yield conditional. Low background support does not universally veto all detection algorithms. No reliability claim is made.
- Background estimation: evaluate candidate count, fraction and occupied spatial cells. Defaults: at least 32 candidates, 1% of image, and 50% occupancy of a 4x4 grid. These are configurable VEGA operational screening heuristics chosen to flag sparse or localized support, NOT NASA requirements or a proof of sufficiency for any estimator. Empty cells are counted; small arrays use at most one grid cell per pixel. If screening passes, status is still conditional until an estimator-specific sufficiency contract is defined. Global and local estimator adequacy are not interchangeable.
- Photometry: distinguishes preliminary surface-brightness measurement, calibrated physical flux, and precise spectrophotometry in nested methods. IMAGE/units/variance/WCS support preliminary work only conditionally. Calibrated flux is blocked without verified pixel solid angles and method-specific calibration/aperture/PSF/background treatment. EPSF absence is reported for that method; EPSF presence is not sufficient. Summing MJy/sr does not produce Jy. Precise spectrophotometry remains blocked without science-grade spectral calibration.
- Temporal comparison: at least two distinct documented observation IDs and times are required. Missing or different bandpasses block direct comparison. Even compatible prepared exposures yield conditional until relative calibration, spectral-response matching and spatial registration are verified. Same-footprint images from different detectors are not assumed directly comparable. No registration/differencing occurs.
- Spectral analysis: WCS-WAVE table availability is evidence only for a retained table. Missing derived spectral maps and science-grade CWAVE/CBAND calibration block precise analysis. The current prior-stage adapter provides no verified solid-angle map, photometric-method calibration or science-grade CWAVE/CBAND product; it reports these as not supplied. It does not infer them from EPSF table CWAVE/CBAND summaries or a successful software test. Supporting future calibration products requires an explicit evidence adapter/method contract; booleans supplied by a caller do not silently promote a method to ready.

Policy.min_analysis_fraction defaults to 10% as an operational detection-support screen. Spatial cell occupancy measures support distribution, not PSF resolution elements, angular area or statistical independence. Noise information is descriptive sqrt(VARIANCE); no unmodeled/correlated uncertainty is assumed absent.

## Reason codes

Identity/IO gate codes: REPORT_MISSING, REPORT_MALFORMED_JSON, INPUT_UNREADABLE, INPUTS_MISSING, EXTRACTION_FAILED, TECHNICAL_FAILED, QUALITY_FAILED, QUALITY_POLICY_UNSUPPORTED, REFERENCE_MISMATCH, IDENTITY_UNPROVEN, IDENTITY_MISMATCH, EXTRACTION_FILE_MISSING, EXTRACTION_HASH_MISMATCH, RESOURCE_LIMIT, MASK_INVALID, MASK_METRICS_MISMATCH, DUPLICATE_PREPARED_PRODUCT, INPUT_CHANGED_DURING_EVALUATION, REPORT_READBACK_FAILED.

Capability codes: SPATIAL_DISPLAY_REQUIREMENTS_MET, IMAGE_MISSING, UNITS_UNVERIFIED, SPATIAL_WCS_MISSING, NO_USABLE_PIXELS, VARIANCE_MISSING, NOISE_INFORMATION_MISSING, INSUFFICIENT_ANALYSIS_SUPPORT, DETECTION_METHOD_NOT_QUALIFIED, BACKGROUND_NOT_ESTIMATED, BACKGROUND_COUNT_LOW, BACKGROUND_FRACTION_LOW, BACKGROUND_SPATIALLY_CLUSTERED, BACKGROUND_ESTIMATOR_UNSPECIFIED, SOLID_ANGLE_MAP_MISSING, PHOTOMETRIC_METHOD_CALIBRATION_MISSING, PRELIMINARY_SIGNAL_ONLY, EPSF_MISSING, SECOND_INDEPENDENT_OBSERVATION_MISSING, OBSERVATION_TIME_MISSING, INDEPENDENT_TIMES_UNPROVEN, BANDPASS_MISSING, BANDPASSES_INCOMPATIBLE, TEMPORAL_CALIBRATION_UNVERIFIED, SCIENCE_SPECTRAL_CALIBRATION_MISSING, SPECTRAL_MAPS_MISSING. Their names identify the failed prerequisite; human context and remedies are also in each capability entry. Consumers must branch on codes/gates, not error-message text.

## Output and downstream gate

Each run creates data/readiness/<UUID>/readiness_report.json exclusively, with strict JSON serialization and readback comparison. A serialization/storage failure propagates rather than reporting success. overall_processing_status=completed means evidence evaluation completed, NOT that all capabilities are ready. failed means identity/inputs could not be trusted; all capability gates are blocked. Schema, policy settings, IDs, input references, current hashes, measured support/distribution, calibration evidence, errors and warnings are retained.

Stage nine may consume a completed readiness report and prepare only methods with allow_preparation=true. It must not treat conditional as permission to execute science: inspect the selected capability/method's allow_scientific_execution and execution_conditions. Blocked calibrated_flux cannot be enabled through the parent photometry preliminary gate. No Algorithm Inputs files are created here.

## Real M101 and tests

Measured from files: 3422 total pixels, 3322 analysis usable, 20 background candidates. Candidates occupy 3/16 cells (18.75%), with cell counts [4,0,0,14,0,0,0,0,0,0,0,0,0,0,0,2]. This fails all three default background screens; it is not hidden by the 97.08% analysis fraction. One prepared observation blocks temporal comparison. Valid spatial WCS/EPSF and retained WCS-WAVE do not supply missing spectral maps or a calibrated photometry method.

Run `python -m pytest -p no:cacheprovider tests` from Data_Preparation_Pipeline. The full regression run passed 184 tests. New tests cover exact real evidence/readback/immutability, missing/malformed/failed/mismatched reports, corrupt/absent/wrong-shape masks, gates, configuration, missing prerequisites, synthetic exposure independence/bandpass/time failures and independently known spatial support patterns. Real data counts are asserted in integration tests for this fixed artifact, never imposed by the implementation.

Scientific sources: https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/ ; https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/ ; https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/sp.html . Readiness is a data/prerequisite assessment, not algorithm execution or a validated scientific result. The prior quality policy and missing spectral calibration limitations remain applicable.
