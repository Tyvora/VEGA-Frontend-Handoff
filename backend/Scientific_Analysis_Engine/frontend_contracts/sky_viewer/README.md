# Sky Viewer specification

## Layout and controls

Shared target header and warning tray remain visible. Left: observation rows with time, detector/bandpass and processing version. Center: image, fit/zoom controls, scale/readout status. Right: selected observation, IMAGE unit, measurements, WCS and provenance. Mobile uses the shared drawer/stack pattern. Filter detector/bandpass only when actual metadata exists; unknown is labeled Unknown, never guessed from wavelength color.

Core: delivered preview, product selection, pan/zoom, unit/identity, warnings, fit and original aspect ratio. Conditional: backend cursor RA/Dec and intensity, source overlay, masks, measurement details, ZODI/background layers. Advanced: stretch and colormap (gray default, viridis/magma optional), WCS header and original FITS reference. Hide or disable unsupported controls with a reason; do not render an empty catalog as a completed source search.

Observation selection keys on product_id, displays observation_id separately and invalidates pending cursor reads. All images are product-scoped; measurements and overlays must join the same product/WCS. No adjacent product automatically shares the selected measurement. Show MJy/sr as surface brightness, not integrated Jy flux. VARIANCE is (MJy/sr)^2, not sigma; any sigma must be explicitly derived and labeled by backend. An empty uncertainty is Not reported.

## FITS-to-browser contract

Source data are prepared IMAGE/VARIANCE/FLAGS/masks and full WCS; these are not browser RGBA pixels. Future backend renders a display-only PNG from finite IMAGE values using recorded low/high/method/colormap. Preserve NaN/invalid pixels as transparent over checkerboard; a mask overlay is visually distinct and has a legend. low < high must be checked by formatter (JSON Schema cannot compare arbitrary fields); log rendering excludes nonpositive samples and reports the excluded region. Colors/stretches never change measurement values.

Native preview uses detector axes with science y up. science_shape is [ny,nx], raster_dimensions are width,height. Browser raster coordinates have edges (0,0) at upper left and centers (u+0.5,v+0.5). Apply raster_edge_to_science_pixel_affine BEFORE WCS: for native equal-size W×H, x=u-0.5 and y=H-0.5-v. Pixel center (0.5,0.5) maps to science (0,H-1). Reduced previews require scale terms in this supplied affine. CSS screen coordinates first convert through viewer viewport to raster edges. Do not use CSS pixels directly. science x is column and y is row, origin 0. Bounds are checked by backend.

Full TAN-SIP mapping belongs to backend Astropy. Do not linearly interpolate RA/Dec, discard SIP or assume north-up. A north-up reprojected display would require a new WCS/grid and asset contract revision; this baseline keeps native orientation. Cursor POST is proposed only. Debounce to ~100 ms, include request_sequence, discard responses for old product/sequence. For outside/masked/nonfinite pixels display status and no fabricated value. Wavelength and bandwidth readout remain null: WCS-WAVE alone is not calibrated spectral inference.

Default single PNG is sufficient for current small cutouts (inspected first product 59×58). Propose DZI above configurable 4096 px dimension or browser texture constraints after measurement; this threshold is engineering policy, not proven benchmark or science limit. Tiles retain the same raster-to-science affine. First show low-resolution preview, then tiles lazily. Never download full FITS on page load. Backend-only conversion is a chosen architecture, not an implementation in this task.

## Field mapping and interactions

Required root target/state/features/issues/provenance give identity and eligibility. data.observations supplies products, times and preview references. data.selected_product_id links into observations. data.image supplies asset, science_shape, raster dimensions, unit/original_unit, affine, stretch and WCS interaction. data.available_layers lists delivered layer names, not promises of analysis. data.source_overlay includes items, method/version, validation and its own execution/readiness; unavailable requires an empty items list. data.scientific_products carries optional-content references to future algorithm outputs; the array is required but may be empty.

Mask/ZODI previews and future background models must be delivered as assets with product/grid association before enabling a layer. They cannot be synthesized from the mock image. Source markers use celestial positions projected by a verified backend overlay adapter; their table alternative is keyboard accessible. Clicking a marker opens method, units, uncertainty and validation. Brightness is read from science data, never PNG sampling.

Mocks: example is renderable UI, loading has no image, partial retains a usable image with warning, empty has no matching observation, unavailable has no renderer/capability, error contains an error. Keep target/header on all failures. Failed assets show metadata and Retry without inventing a substitute sky image. Switching products cancels old asset loading; a race cannot attach the prior result.

## Acceptance checks

Validate every response with response.schema.json and shared registry. Exercise all six fixtures, aspect ratio and affine center/corners, disabled mock cursor API, visible units and masks, safe unknown metadata and warning persistence. Real integration must add a FITS↔sky roundtrip tolerance check (proposed 0.001 pixel, validated for each WCS) and provenance-backed readouts; fixture tests do not establish those science capabilities.
