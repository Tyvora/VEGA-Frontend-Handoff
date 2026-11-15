# Timeline specification

## Layout and workflow

Show a chronological strip/list with exposure start/end, explicit time scale, product ID, observation ID, detector/bandpass and version. Main region has a single-frame viewer, Previous/Next, observation selector and paused blink speed slider (250–2000 ms). Side-by-side opens two native-grid panels. Inspector shows alignment/compatibility and exclusion reasons. Filter by detector/time/compatibility; missing times appear in an Unknown time group and do not receive an invented sort timestamp. Keyboard previous/next and Pause must remain available.

Use observations as metadata, not a claim of independent exposures. Preserve product and observation identity; pages may include multiple products of the same exposure. Numeric time sorting must use backend normalized time after explicit time-scale conversion; display ISO UTC only when present. MJD is labeled with its actual scale. A detector label alone does not establish wavelength compatibility, especially for SPHEREx spatially varying spectral response.

## Two comparison modes

Visual browse is the baseline: native frames or side-by-side with unaligned badge. Blink may be allowed explicitly as visual_only and must say “Unaligned visual browse — apparent shifts/brightness changes are not measurements.” No automatic candidate extraction or science claim follows. Same stretch is useful for exploration but does not normalize different spectral responses or calibrations. Start paused, honor reduced motion, preserve acquisition order and expose missing masks/data.

Scientific comparison requires delivered compatibility group: verified compatible bandpass, registered_verified alignment, verified calibration, mode scientific, scientific_comparison true, authorized ready group assessment and executed algorithms. Difference additionally requires difference true and a real difference_asset. Frontend does no science subtraction or reprojection. The schema rejects a scientific flag on unknown/unaligned groups; the service must prove that flag with report references, independent exposures, PSF/grid/unit/calibration and processing-version compatibility. Different versions are shown, not silently normalized.

Three prepared products do not establish group temporal readiness. Current workflow group_temporal_readiness is not_evaluated, and current temporal comparison is blocked. Production science controls remain disabled; mock blink is solely synthetic visual browsing. Registration, compatibility and difference computation are future algorithm responsibilities.

## Data and components

Required data.observations includes times, preview, WCS and quality references. selected_product_ids references currently loaded rows. compatibility_groups names member products, bandpass_status, alignment_status, calibration_status and eligibility with reasons. difference_asset is null unless available. page carries returned/has_more/next_cursor; load 50 rows initially (proposed policy), virtualize long lists and lazy-load the selected frame plus one neighbor. Retain selections across pages via stable IDs and a service lookup; never silently drop an off-page selection.

Scientific products reference compatibility_assessment, registered_image, crossmatch_table and difference_image outputs with method/version/provenance; future physical photometry uses Measurement values/uncertainties, not image color. Plotly time series is enabled only with real measurements, units and time scales. It is absent in the current mocks.

Switch tabs without changing target/request, keep timeline cursor and paused state. Clicking evidence selects known product IDs, validates context and shows unavailable if absent/unauthorized. Image load failure marks just that frame; continue other frames and pause blink if an operand fails. Timeout never becomes zero variation.

## State acceptance

example.mock.json: two synthetic frames, visual-only unaligned blink, no scientific difference. Loading: indeterminate with preserved context. Partial: retain available rows and show missing subset. Empty: successful query no observations. Unavailable: no capability/assets. Error: service failure with scoped retry. Validate all six. Acceptance includes exact boundary speed values, explicit UTC/MJD labeling, disabled scientific difference and no readiness promotion from row count.
