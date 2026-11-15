# Discoveries specification

## Purpose and layout

Display algorithm-produced **candidates**, never confirmed discoveries. The current engine has no candidate algorithm; production defaults to Unavailable. A successful implemented search finding zero would be Empty instead. Synthetic example cards are explicitly MOCK and provide no astronomy evidence.

Left/list: type, position, supporting-observation count, quality warning and validation badge. Detail region: evidence panels, observation history, method/version, measurements with units/uncertainties and missing requirements. Candidate filters: type, review state, time interval and availability of evidence; backend-supported filters only, with no arbitrary confidence threshold. Header shows displayed/returned counts and pagination, not an unsupported global total. Order by supplied backend order; no invented ranking score.

Candidate categories reserved in schema: moving_source, brightness_change, newly_visible, disappearing, unclassified_anomaly. Expose only available_candidate_types actually supplied by the service. These labels are not promises that any detector exists. Newly visible/disappearing need comparable sensitivity, masks and coverage; absence alone is not a disappearance. Motion needs independent timed positions, astrometric uncertainties and association checks. Brightness changes need compatible spectral response/calibration and propagated uncertainty.

## Field and evidence behavior

Every candidate has candidate_id, candidate_type, ICRS position, supporting_observation_ids, evidence, measurements, uncertainty_status, validation_status, detection_method/name/version, warnings and missing_scientific_requirements. motion is nullable. Evidence includes both product_id and observation_id, asset, reference/comparison/difference role and mock flag. These identities cannot be interchanged. Count distinct supporting observation IDs as supporting observations; do not label it an independent-detection count without an executed association/compatibility result.

Position is a catalog/result estimate, not a predicted moving-object ephemeris. No uncertainty value means Not reported, never ±0. Measurement records carry name, canonical unit, nullable value, uncertainty status/value and method/version. Reported uncertainty must be numeric and nonnegative. No confidence_score field exists. Candidate review states unreviewed/reviewed_candidate/rejected never imply external confirmation. Root scientific_validation is separate from candidate review and algorithm execution.

Motion displays a track only when actual motion output exists, with observation-linked time reference, model and uncertainties. The compact motion object is a summary; data.scientific_products points to the full motion_track asset containing timed positions. Do not connect raw ICRS longitudes with a straight pixel line across RA wrap; use the verified projection service and unwrap on the backend. Brightness charts require actual photometry; do not chart mock stretch bounds as flux. No motion or physical chart is enabled by the current single synthetic candidate fixture.

Evidence opens Sky Viewer at its product/position and Timeline at its supporting observations; preserve request/run/target and candidate ID. Resolve opaque references through the API, not local Windows paths. Missing asset keeps the card and displays Evidence unavailable. Never substitute another target's preview. Quality panel shows method, version, provenance, warnings and missing requirements; unknown is visible rather than hidden by an attractive badge.

## States and acceptance

example.mock.json is a renderable synthetic unclassified candidate, unreviewed, with a watermarked evidence SVG. Loading shows skeleton without fabricated candidate counts. Partial shows usable cards plus missing-product warnings. Empty means a successful implemented query with zero matches. Unavailable says Algorithm not implemented / requirements missing. Error uses error code and retry guidance. Candidate count never implies verified discovery.

Validate all six fixtures and all evidence joins. Check required labels, unavailable/empty distinction, absent uncertainty, no score or confirmed label, keyboard evidence inspection, context-preserving navigation and lazy evidence loading. Scientific production candidates require completed execution, ready authorization and execution_reference. Report validation alone is insufficient to establish external truth; backend provenance verification is mandatory.
