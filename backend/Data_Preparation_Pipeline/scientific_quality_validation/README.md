# Scientific Quality Validation

This stage applies a reproducible **VEGA operational quality policy**, not a universal SPHEREx science certification. It leaves IMAGE, VARIANCE, FLAGS and ZODI unchanged. It performs no detection, photometry, background subtraction, cross-matching, spectral-map reconstruction or analysis readiness.

## Technical gate and provenance

`evaluate_quality(extraction, technical_report)` requires passed/passed_with_warnings technical status, no technical errors, eligibility=true, matching extraction path and request/product/observation IDs. Hashes of arrays.npz, tables.fits, metadata.json and report.json must match the technical report before work starts and after evaluation. This prevents reusing technical acceptance after extracted files change. Failures save a failed report and no newly evaluated masks. Existing failed output directories must not be consumed. Outputs are unique UUID subdirectories under data/quality.

## Policy vega-dr1-qr3-conservative-1.0

Definitions are read from the actual FLAGS MSKNnnnn/MSKDnnnn cards in preserved headers. Names AND positions are compared to the current official SPHEREx introduction's published table. Product processing version and collection are recorded. Differences are not silently remapped; active unmatched bits are unknown and excluded conservatively. The header descriptions and reference agreement are recorded. No fallback assumes FLAGS!=0 is bad.

VEGA classifications:

- Critical/excluded from analysis: TRANSIENT, OVERFLOW, SUR_ERROR, NONFUNC, DICHROIC, MISSING_DATA, HOT, COLD, NONLINEAR, PERSIST, CROSSTALK, GHOST, GHOST_FPA, GHOST_EXT, STREAK, BLOOM, SNOWBALL, HALO. This conservative exclusion is an explicit VEGA choice informed by descriptions and the official source-discovery example's conservative bad-photometry list, not a statement that each flagged pixel is unusable for every task.
- Warning/caution: PHANMISS and OUTLIER. Retained for analysis but excluded from background candidates. This is a VEGA choice and may need stricter settings for a particular algorithm.
- Source/background exclusion: SOURCE is retained for analysis and excluded only from background candidates.
- Informational: FULLSAMPLE is retained.
- Unknown: undeclared or mismatched bits are counted and excluded conservatively, including the sign bit of signed FLAGS. Bitwise decoding uses the original integer width, not a boolean cast.

## Masks and reasons

analysis_mask=True requires finite IMAGE, finite positive VARIANCE, no critical and no unknown flags. background_mask=True additionally requires no SOURCE or caution flags. It is a candidate set, not a background estimate. There is no dilation or arbitrary spatial exclusion. Background mask is always a subset of analysis mask. Zero analysis-usable pixels gives failed; zero background candidates is only a warning. No percentage threshold declares general scientific goodness.

masks.npz stores both boolean masks and uint8 exclusion reason maps. Bit values: 1 IMAGE nonfinite, 2 VARIANCE nonfinite/nonpositive, 4 critical, 8 unknown, 16 SOURCE (background only), 32 caution (background only). Multiple reasons can coexist; category counts are unions of pixels, while per-flag counts can overlap. Original flags are not rewritten.

## Metrics and units

quality_metrics.json records counts and fractions, individual flag definitions/counts/categories, invalid/nonpositive variance, IMAGE/VARIANCE NaN/Inf, analysis/background fractions, variance and sqrt(VARIANCE) min/median/max and 5/25/75/95 percentiles. Noise summaries use only analysis_mask=True pixels; sqrt(VARIANCE) is descriptive and does not replace the original variance. Its unit is the square root of the actual variance unit. No claim of independent pixels or complete uncertainty accounting is made.

ZODI summaries use all finite ZODI values. Missing or nonfinite ZODI causes a warning, without automatically excluding an analysis pixel. The model is not subtracted and is not assumed to represent all astrophysical background components.

quality_report.json records IDs, technical reference, policy version, flag sources, shape/dtype/meanings/reason encoding, counts, technical capabilities, warnings/errors and quality_status. Detailed variance/ZODI statistics are in the companion metrics file. Status passed/passed_with_warnings/failed describes this policy only. ready_for_analysis_readiness is a handoff indication, not execution of that stage. Read report status before consuming masks. Report/filesystem write errors propagate; no successful completion is claimed if outputs cannot be stored.

## Usage and testing

```python
from scientific_quality_validation import evaluate_quality
report, folder = evaluate_quality(
 'data/extractions/1ff9732e-6d34-47fe-a479-ce385ceeef35',
 'data/validation/technical-a34702f2-8963-4afe-8bb1-6d48ac6c75b6.json')
```

Run `python -m pytest -p no:cacheprovider tests` from Data_Preparation_Pipeline. The full suite passed 157 tests. Synthetic expectations cover simultaneous flags, SOURCE-only and informational pixels, critical/caution/unknown bits, signed sign-bit preservation, NaN/Inf, invalid variance, missing/nonfinite ZODI, independent expected masks/statistics and input immutability. Integration tests use real M101 data, persisted masks/reports and critical technical/hash rejection.

## M101 evidence and limitations

3422 pixels; analysis usable 3322 (97.0777%); background candidates 20 (0.58445%). Critical flags affect 100 pixels, caution 1, SOURCE 3401, unknown 0. IMAGE/VARIANCE are finite throughout and variance is positive everywhere. Therefore numeric validity alone would have missed the 100 excluded pixels. Missing spectral maps remain a technical capability limitation and do not become available in this stage. Only 20 background candidates must not be interpreted as sufficient support for a future background estimator.

The policy matches the actual processing VERSION=7.0.5 header names and bit positions to the current official tutorial. It is not a certification for unseen processing versions. The current Explanatory Supplement PDF (Table 16 referenced by the product documentation) could not be fetched by the documentation browser during this run; definitions were corroborated from original headers and official published tutorial, not guessed. No empirical scientific calibration or task-specific policy optimization was performed.

References:
https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/ (MSKN/MSKD, flags and variance)
https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/ (Level 2 products; Table 16 reference)
https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/sp.html (known-source masking for background)
https://caltech-ipac.github.io/irsa-tutorials/spherex-source-discovery-tool-demo/ (conservative bad-photometry flag example; context-specific, not a universal veto list)
https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp.pdf (direct fetch unavailable)
