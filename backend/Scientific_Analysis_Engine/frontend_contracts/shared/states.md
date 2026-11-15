# Shared states and semantics

Contract version 1.0.0 uses JSON Schema Draft 2020-12. All times with iso_utc use RFC3339 UTC; MJD has an explicit scale and d unit. Keep observation metadata time and report-generation time distinct. Null is unavailable/unknown, not zero. Product ID identifies an archive product; observation ID identifies a recorded exposure; multiple products can share one observation. Target ID is a service-scoped selection identity, not a catalog designation.

| Axis | Values | Meaning |
|---|---|---|
| backend_processing.status | pending, running, completed, partial, failed, cancelled | Orchestration/service work, not scientific validity |
| data_readiness.status | ready, conditional, blocked, not_evaluated | Capability decision with original reasons and execution conditions |
| algorithm_execution | not_implemented, not_run, running, completed, failed | Whether an algorithm actually ran |
| scientific_validation | not_evaluated, unvalidated, validated, rejected | Independent result assessment, not preparation success |
| ui_availability | loading, available, partial, empty, unavailable, error | What the tab can display |

A completed preparation workflow can yield available imagery and unavailable Discoveries. Conditional allows package preparation when the report says so, never scientific execution. The schema forbids allow_scientific_execution for conditional/blocked/not_evaluated. Ready is necessary but not sufficient: explicit execution permission is required. A validated result needs non-mock science_result, completed execution, authorized readiness and an external validation reference. Schema checks the reference's presence; authenticity requires backend verification.

UI available is the “ready example” state name, avoiding overloaded ready. Loading requires pending/running processing. Error requires an error item. Empty is a successful selection/query returning zero entries, never an absent algorithm. Partial means usable subset plus scoped warnings; it never authorizes an unready comparison. Unavailable can be expected and nonretryable. Existing pipeline stage skipped maps to a per-feature unavailable reason STAGE_SKIPPED; it is not silently converted to completion. The proposed Job reports workflow state; scientific capability decisions stay in the result and are not aggregated away.

Per-feature keys (image_display, pixel_readout, blink, difference, source_overlay, candidate_list as needed) contain availability, allow_interaction, implementation_status and reason_codes. Unavailable always disables interaction. Planned APIs cannot be called merely because a mock displays an image. A frontend may display the most restrictive combination of result, feature and per-item eligibility; it must never relax one gate because another says available.

Issues use stable code/message/severity/scope/retryable. Scope examples: response, product:<opaque-id>, candidate:<id>, feature:pixel_readout. Show nonretryable scientific limitations in the inspector; retryable transport failures get Retry. Error messages must not leak server paths or credentials.

Source reports are preserved in provenance.references, methods/versions and validation_reference. No browser should treat a reference string as proof: service authorization resolves it. Real archive_metadata is not an algorithm result; science_result is only populated after execution. Scientific products carry independent provenance and validation. Mock root, candidates, evidence and derived products remain labeled synthetic and cannot be validated.

Schema validation does not compare arbitrary IDs across lists or interpret time scales. Service invariants: selected IDs belong to current search/request, observation evidence joins are consistent, timestamps are finite/ordered after time-scale conversion, page.returned equals actual returned items, next cursor belongs to current filters, assets are authorized and immutable. Nonfinite parsing is rejected before schema validation.
