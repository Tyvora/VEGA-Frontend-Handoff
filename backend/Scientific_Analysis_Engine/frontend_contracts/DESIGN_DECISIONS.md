# Design decision records

Evidence keys link to [research sources](RESEARCH_REPORT.md); local evidence is the inspected pipeline README/package/report set. These decisions specify future implementation, not deployed capabilities.

| Decision | Alternatives | Selected approach | Reason | Evidence | Impact |
|---|---|---|---|---|---|
| Navigation | Independent pages; hybrid; tabs | Three tabs in one Explorer Workspace with deep links | Retain target/run and evidence context for non-specialists | Existing three goals; ESA explorer precedent; explicit VEGA UX judgment | Shared context, per-tab state, back navigation |
| Image display | Browser FITS; raw Canvas; WebGL; full archive stack | Backend PNG plus OSD; optional DZI | Current cutouts small; avoid implementing a second science reader | Real 59×58 package; OSD docs | Renderer/asset service needed later |
| Large imagery | Eager full image; tiles | Configurable 4096px trigger then benchmark; lazy tiles | Bound memory and delivery | OSD tile guide; engineering policy, no benchmark claim | Immutable pyramid/affine metadata |
| WCS | Linear RA interpolation; browser projection | Backend Astropy full distortion | Preserve TAN-SIP and origin convention | Actual WCS header; Astropy WCS docs | Cursor request/response with sequence protection |
| Orientation | Auto north-up; native | Native detector y-up, explicit affine | Avoid silent reprojection and pixel displacement | Package row/column convention; OSD coordinate guide | Exact center-offset transform required |
| Measurement | RGB inference; scientific readout | Original arrays/backend, units and masks | Preview quantization cannot be photometry | SPHEREx product docs; source arrays | No science from colormap |
| Plots | Custom canvas; chart libraries | Lazy Plotly error bars only when measurements exist | Established chart support, no need for WCS plots | Plotly error-bar and license docs | Optional dependency and accessible table |
| Timeline | Scientific blink by default; browse-only | Native visual-only until verified group | Products are not automatically independent/comparable | Workflow group not_evaluated; blocked temporal gate | Difference and science controls disabled |
| Discoveries | Confirmation/confidence badges | Unconfirmed candidate/evidence/method/uncertainty | No calibrated score or external confirmation exists | Empty algorithm scaffolds; Backyard Worlds evidence approach | Unsupported types unavailable |
| Status | One ready flag | Five axes plus feature/per-item gates | Preparation, execution, validity and display differ | Real readiness reports | Conditional never authorizes science |
| Run creation | Auto-download all; target-only run | Resolve/validate, search, explicit product selection, saved-request run | Existing runner requires selected IDs and identity-matched cached search | Public orchestrator README | Two-phase API, max three selected in proposal |
| Progress | Synthetic percentages; SSE | Stage/product polling with optional measured fraction | Runner provides checkpoints, no event server exists | Existing workflow manifests | 1–5s backoff, ETags; no fabricated percent |
| Delivery | Expose files as API; inline FITS | Proposed JSON/asset API and opaque refs | Local files are not browser services | No API/result_formatter implementation | Implement adapters separately |
| Fixtures | Real-looking NASA results; network-dependent mocks | Labeled synthetic JSON plus original SVG | Exercise UI without scientific fabrication | Contract tests and watermark | Mock flag persisted in every candidate/evidence |
| Licensing | Adopt broad sky SDK now | BSD OSD/MIT chart/shell, no copied UI | Sufficient initial scope; Aladin license discrepancy unresolved for a release | Upstream license files | Pin/review exact releases before deployment |
