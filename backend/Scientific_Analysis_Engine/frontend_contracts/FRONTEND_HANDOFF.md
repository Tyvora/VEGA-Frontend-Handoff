# VEGA — Frontend developer handoff

## Scope and current truth

VEGA lets a non-specialist explore NASA SPHEREx observations through **Sky Viewer**, **Timeline**, and **Discoveries**. This delivery supplies complete presentation contracts and development fixtures. It implements no frontend, API, Result Formatter or scientific algorithm.

The inspected preparation pipeline already exposes create_request, validate_request, search/archive interfaces, run_pipeline, package readers and readiness reports. Read their public documentation before connecting a service adapter: [User Input](../../Data_Preparation_Pipeline/user_input/README.md), [Request Validation](../../Data_Preparation_Pipeline/request_validation/README.md), [Archive Search](../../Data_Preparation_Pipeline/archive_search/README.md), [Orchestrator](../../Data_Preparation_Pipeline/orchestrator/README.md), [Algorithm Inputs](../../Data_Preparation_Pipeline/algorithm_inputs/README.md), [Readiness](../../Data_Preparation_Pipeline/analysis_readiness/README.md).

Three M101 DR1 D3 products have prepared packages; this proves package reading, not scientific results. In the inspected workflow, sky visualization is ready, source detection and photometry conditional, background/temporal/spectral blocked; group temporal readiness is not evaluated. No group result is inferred here. The engine's ten algorithm folders and result_formatter are scaffolding. Current UI production fallback is unavailable where a formatted result/asset does not exist. The mock ready example means the UI can render a fixture, not scientific readiness.

## Journey and navigation

1. Landing workspace shows target form: input method Name / RA-Dec / Preset, goal, FOV. Name is a catalog string; coordinates accept numeric degrees or explicit sexagesimal units, never infer an unmarked RA hour value. Preset IDs come from backend's versioned list (existing m31); do not invent a public preset list. FOV defaults 0.1 degrees, circular angular diameter; operational range 0.001–1.0 inclusive.
2. Resolve and validate. Retain entered text on failure. Unknown, ambiguous, service-unavailable and resolver errors have distinct messages; offer coordinate entry or retry, never choose a candidate automatically. Known moving objects cannot be treated as fixed catalog positions.
3. Retrieve metadata; show product rows with product ID, observation ID, time scale, detector, version, eligibility and completeness warning. Require explicit selection, initially one, at most three in the proposed service. Show budgets before starting; do not download an entire search automatically.
4. Start a bounded asynchronous run using the saved request and search references. Show stage/product status, errors and cooperative cancel. Percentages are indeterminate unless actually measured.
5. Enter **one Explorer Workspace with three tabs**. Keep target header, request/run IDs, warning tray and observation drawer shared. Initial active tab follows request.goal. Switching tabs retains the target and per-tab selection/zoom/filters, does not mutate the original request.goal and does not authorize another scientific computation.
6. Inspect results. Evidence action from a candidate opens Sky Viewer at its product/position or Timeline with its supporting observations. Preserve candidate selection for Back. Empty results, missing algorithms and network errors use different screens.
7. A new target explicitly creates a new request context; cancel/invalidate obsolete fetches. Browser back restores prior workspace state without mixing result contexts.

Use deep links such as `?target=<opaque-id>&view=timeline&product=<encoded-product-id>&candidate=<id>`. Product IDs can contain ? / #; URLSearchParams must encode them. Never derive observation identity by splitting a product string. Shared context keys are request_id/run_id/target_id; per-tab state is separate. A tab may show unavailable while another displays an image.

## Components and responsive behavior

Desktop: target header, tabs, collapsible observation list (280 px design target), flexible image/plot region, 320 px inspector. These widths are UX defaults, not scientific limits. Below 900 px use a drawer and stacked inspector; below 600 px use a single-column viewer, accessible tabs and a bottom observation selector. Avoid horizontal page scrolling. Minimize mandatory controls: fit image, zoom, observation, warnings; advanced panel holds stretch/layers/WCS/provenance.

Shared components: TargetForm, ProductSelector, ProcessingPanel, ReadinessBadge, WarningTray, ObservationDetails, AssetViewer, ProvenancePanel, EmptyState and RetryAction. Status text must accompany color. Tabs implement keyboard arrows/Home/End and aria-selected; controls have accessible names, visible focus, touch targets, and numeric input labels with units. Image canvas has a text metadata alternative. Announce stage transitions via polite aria-live without streaming cursor values. Respect prefers-reduced-motion: blink starts paused and never autoplays.

## Rendering stack and responsibility boundary

Use a React/TypeScript shell (proposed), OpenSeadragon for pixel-image pan/zoom and optional DZI tiles, and lazy-loaded Plotly.js for actual time-series measurements/error bars. Neither library supplies SPHEREx scientific calibration. Backend Astropy owns full TAN-SIP WCS and scientific pixel readout. See [research](RESEARCH_REPORT.md) and [decisions](DESIGN_DECISIONS.md).

Backend, later: read verified packages, preserve readiness gates, execute only authorized algorithms, format versioned JSON, render PNG/native-grid previews, produce immutable assets and supply proposed API. Frontend: validate payload, select view, display delivered assets, pan/zoom, request readouts, show warnings and format units. Frontend must not derive science values from PNG RGB, synthesize difference images or promote readiness.

Files on disk are inputs to a future service, not HTTP endpoints. Do not expose Windows paths. Map file/report references to opaque IDs and asset URLs through the future formatter/API boundary. See [API_PROPOSAL](shared/API_PROPOSAL.md).

## Schema integration

Use Draft 2020-12, not Draft 7; configure Ajv's 2020 class plus formats in a future frontend, and preload all four schemas by $id. Never fetch https://vega.example: these are identifiers, not hosted endpoints. Preserve relative $ref resolution. Validate at the adapter boundary before rendering; reject invalid payloads with a visible CONTRACT_INVALID error and retain the last good result only as explicitly stale. Do not silently strip unknown fields. A schema_version other than 1.0.0 needs a compatible adapter or an unsupported-version state.

IDs are opaque strings in presentation contracts; request_id/run_id may be null before they exist. The actual pipeline request UUID is preserved by a future adapter. Presentation schema_version is distinct from input_contract's schema version. Canonical units include MJy/sr and (MJy/sr)^2; original_unit retains source spelling. No NaN/Infinity JSON: represent missing science values as null plus reason/status, never zero.

Schema alone cannot prove scientific authenticity, identity joins, finite JSON parsing, time ordering or cross-reference membership. The service must verify these and provenance. The contract tests exercise fixture joins and forbidden scientific combinations. Do not use schema acceptance as external scientific validation.

## Local mock development

From frontend_contracts run `python -m http.server 8000 --bind 127.0.0.1`. This serves static files only. Open http://127.0.0.1:8000/sky_viewer/example.mock.json or fetch it in your own development application (configure its dev proxy to the local static server). There is no application page in this delivery. For a standalone browser developer console on that origin:

```javascript
const responseURL = new URL('/sky_viewer/example.mock.json', location.origin);
const payload = await (await fetch(responseURL)).json();
const previewURL = new URL(payload.data.image.asset.href, responseURL);
console.log(payload.state, previewURL.href);
```

Resolve fixture asset.href relative to the response file URL, not your SPA route. Each view provides example.mock.json (renderable/ready UI), loading.mock.json, partial.mock.json, empty.mock.json, unavailable.mock.json and error.mock.json. Swap the fixture URL to exercise states without an algorithm server. Keep the MOCK banner and SVG watermark. Cursor WCS is disabled in fixtures because no readout API exists. Fixture positions/times/brightness stretch are synthetic layout values. The mock SVG is not a scientific FITS preview.

## States and acceptance

Loading retains target and shows indeterminate progress, disables unavailable actions, supports cancel. Partial retains usable products and scoped warnings; retry failed products without discarding successes. Empty means a successful query with zero matching records; unavailable means absent capability/dependency. Error shows a stable code/message, retry only if retryable and keeps input. See [five independent state axes](shared/states.md). Never label an unavailable candidate engine as “zero changes detected.”

Sky Viewer acceptance: one product loads the fixture with original ratio, correct pixel affine and visible unit; product switching cannot display an old cursor response; NaN has no intensity; overlays and pixel readouts remain disabled when unavailable; warnings/provenance are inspectable; zoom/fit keyboard access works.

Timeline acceptance: exact product/observation identities and time scale visible; previous/next and speed 250–2000 ms work while paused by default; native-unaligned blink says Visual only; no difference control enabled without explicit eligibility and a difference asset; three rows alone never enable scientific comparison.

Discoveries acceptance: candidate cards always say Candidate, mock examples say MOCK; evidence keeps product/observation IDs, position and method/version; missing uncertainty says Not reported; no fake confidence score; evidence links retain context; unavailable and valid-empty differ; no Confirmed Discovery label.

## Delivery order and checklist

- [ ] Shared Explorer layout, tabs, target context and browser navigation.
- [ ] Target search form, explicit units, FOV validation and separate resolver error handling.
- [ ] Shared status components and all six fixtures per tab; schema validation first.
- [ ] Image loading, aspect ratio, fit/zoom, failure fallback and pixel transform.
- [ ] Sky Viewer metadata, warnings, optional layers and disabled unsupported controls.
- [ ] Timeline observation browsing, pause/speed, side-by-side and comparison gates.
- [ ] Discoveries candidate/evidence UI, mock banner and absent-measurement states.
- [ ] Scientific warnings, uncertainty and provenance persistent through navigation.
- [ ] Responsive layout, keyboard, reduced motion and screen-reader text alternatives.
- [ ] API integration only after proposed routes are implemented and contract-tested; mock mode must remain explicit.
- [ ] Real assets/readout WCS roundtrip and sequence tests; no claims of scientific verification from mocks.

Backend team must later provide target/preset endpoint, persisted request/search IDs, selected-product run service, identity authorization, readout/rendering service, immutable asset registry, cancellation acknowledgements, result_formatter and real algorithm outputs with calibrated uncertainties. They must assess group temporal compatibility separately. The current handoff is sufficient to build and test presentation in mock mode immediately; production science awaits these dependencies.
