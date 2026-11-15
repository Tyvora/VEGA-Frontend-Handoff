# Proposed delivery API — NOT IMPLEMENTED

No route below is deployed. These are same-origin HTTPS design contracts for a future service adapter. Version prefix is /api/v1; response schema version is separately 1.0.0. Disk files → verified public package reader/reports → future result_formatter → API/asset authorization → frontend. A stored JSON file is not an API. Do not expose arbitrary filesystem paths or let user-supplied asset IDs select local files.

## Operations

Payload names refer to common.schema.json/$defs unless a view schema is named. Reject additional fields; enforce finite JSON, authentication/context ownership and referential identity in the service. Requests are application/json; response errors use ApiError. IDs are opaque, encoded URL path components.

| HTTP operation (all proposed) | Request/query | Success response | Failure/status behavior |
|---|---|---|---|
| GET /presets | none | 200: version string, presets array of {id,label,position:Position,reference}; existing User Input list only | 503 ApiError |
| POST /targets/resolve | TargetInput | 200 ResolveResponse with saved request_id, Target and accepted validation; rejected result remains rejected | 422 invalid/unknown/ambiguous target, 502 resolver_error, 503 service_unavailable; ApiError |
| POST /searches | SearchRequest | 200 SearchResponse, saved search_id bound to request_id, metadata only | 409 rejected request, 503 archive unavailable; partial rows explicitly status partial |
| GET /searches/{search_id} | cursor optional, limit 1–100 default50 | 200 SearchResponse for same request/filter snapshot | 404/410 absent/expired search, 400 invalid cursor |
| POST /runs | StartRun | 202 Job; Location: /api/v1/runs/{run_id} | 409 identity/idempotency conflict, 422 missing/ambiguous/nonmember selected ID or limits, 503 queue unavailable |
| GET /runs/{run_id} | If-None-Match | 200 Job with actual workflow status, stage, selected/completed counts; 304 unchanged | 404 unknown, 403 unauthorized |
| POST /runs/{run_id}/cancel | CancelRequest, run_id must match path | 202 Job cancel_requested true, cooperative acknowledgement | 409 already terminal; stop status only after acknowledgement |
| GET /runs/{run_id}/results/{view} | view enum sky_viewer/timeline/discoveries; cursor/limit for list views | 200 matching view response.schema.json, including partial/empty/unavailable; ETag | 202 Job before result exists; 404 absent run; 500/503 ApiError |
| POST /pixel-readouts | PixelQuery within authorized run context (X-Run-ID) | 200 PixelReadout, original science pixel and WCS position, never RGB estimate | 404 product, 409 WCS unavailable, 422 invalid pixel; outside status may return value/position null |
| GET /assets/{asset_id} | optional short-lived token, authorized context | 200 PNG/JSON/DZI/tile/FITS per Asset.media_type; immutable ETag/hash | 403 forbidden, 404 missing, 410 expired signed reference; no path traversal |
| POST /runs/{run_id}/display-assets | {product_id,stretch:{method,low,high,colormap}} | 202: {asset_request_id,status:pending}; GET /display-assets/{id} → 200 Asset when ready, 202 pending | 422 invalid range/log constraints; display-only transformation |

GET /presets and display-assets have inline object payloads defined in this table; all others use named machine-readable definitions. A service implementation must add these transport-only envelopes to its OpenAPI without changing scientific units/meaning. No raw source data is returned by a target-resolution call. Real implementation should enforce bounded name length and resolver timeout centrally, not silently truncate input.

## Concrete two-phase lifecycle

1. POST /targets/resolve with `{"input_method":"coordinates","value":{"ra":210.80227,"dec":54.34895},"goal":"sky_viewer","fov_deg":0.1}`. Adapter calls public User Input/Request Validation, saves original accepted request, returns its ID and normalized target. Do not resolve again at run creation.
2. POST /searches with `{"request_id":"<saved-uuid>","max_products":100}`. Adapter saves metadata, returns search_id and explicit completeness. No download occurs.
3. User chooses product IDs from that snapshot. POST /runs with `{"request_id":"<saved-uuid>","search_id":"<saved-search-id>","selected_product_ids":["<exact-product-id>"],"idempotency_key":"<client-generated-key>"}`. Default one product, proposal cap three, never automatic all-products. Service invokes run_pipeline with request_file and cached_search referencing the SAME saved request. Existing public orchestrator supports this reuse; it must not reconstruct a fresh target request with a different ID.
4. Poll run with 1 second initial interval and backoff to 5 seconds, honoring Retry-After and 304. Stage status/counts are factual; progress_fraction null if not measured. Only display result references after service verifies request/product/hash associations. Run completed means preparation complete, not algorithms validated.
5. Retrieve view result, load selected assets lazily and preserve their context. Switching tabs requests a presentation of the same target/run. If a different capability needs additional processing, service must explicitly create/record that work and re-evaluate readiness; tab switching cannot bypass a gate.

Idempotency key is scoped to principal + operation + canonical payload digest: identical retry returns existing run; changed payload with same key returns409. Request/search/run mismatches return409, never reassignment. No assertion of global identifier uniqueness from browser-side checks. Workflow/package public readers remain responsible for integrity.

Example error: `{"request_id":null,"run_id":null,"errors":[{"code":"RESOLVER_UNAVAILABLE","message":"Name service is temporarily unavailable","severity":"error","scope":"target","retryable":true}],"warnings":[]}`. Stable codes drive controls; localized UI text does not change science meanings.

## Assets, caching and failure

JSON encodes metadata, status, small measurements and references; images are separate PNG/DZI. Scientific FITS is an optional explicit download, never a required browser payload. Published assets are content-addressed/immutable with SHA-256; require HTTPS same-origin or an explicitly allowlisted host, CSP and correct Content-Type. Fixture SVG is locally trusted; arbitrary remote SVG must not be executed. DZI asset authorization applies to all tiles. WCS/report references are opaque IDs resolved by service; no browser path access.

Backend rendering cache key includes source hash, product, grid/WCS identity, algorithm/version if relevant and stretch parameters. Changes produce a new asset; never overwrite the meaning of an old URL. Metadata/results use ETag plus private revalidation; immutable authorized assets may use private max-age according to data access policy. Do not cache failures as astronomical answers. User Input's separate Sesame cache retains 7-day success / 1-hour not-found and ambiguous / no service failures; frontend caching does not override that policy. Expired results are labeled stale and never silently substituted for a new run.

Proposed frontend policy: 15-second metadata timeout, 30-second asset timeout, at most two bounded exponential-backoff retries for idempotent reads with jitter; respect Retry-After. Run start retries reuse the idempotency key. Cancellation does not abort a server stage instantly; retain pending acknowledgement and explain it. Existing runner only cooperatively checks time/cancel at supported boundaries; service must not invent a universal preemptive stop.

Large lists: default50, maximum100 per page, opaque snapshot/filter-bound cursor, has_more and next_cursor. Request next page only on explicit More or near-list-end; virtualize beyond 200 mounted rows (proposed UX limit). Avoid a fake total when archive is truncated. Cache only selected and adjacent preview; evict using a configurable LRU budget. Tile for large rasters, abort obsolete requests and discard out-of-order responses. Partial asset/network failure does not erase readable products. No performance claim is made without browser profiling.
