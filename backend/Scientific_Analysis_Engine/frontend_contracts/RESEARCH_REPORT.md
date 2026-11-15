# Research report — astronomy results on the web

Reviewed 2026-11-15. Method: official documentation, original repositories/license files, and read-only inspection of existing VEGA packages/reports. No browser benchmark, usability study or library integration was run. Capability claims below are documentation-based; choices and thresholds are engineering judgments. Documentation accessibility is not evidence that every hosted data service works.

## Astronomy interface comparison

The two tables jointly cover problem, image/coordinates/navigation, time, sources, evidence, adaptation, exclusions and reusable software/licensing for every reference. “Not established” means the reviewed source did not establish the capability, not that the project lacks it.

| Reference and primary evidence | Problem, imagery, coordinates and navigation | Time, sources and candidate evidence |
|---|---|---|
| NASA/IPAC IRSA SPHEREx [visualization help](https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/visualization.html) | Archive result exploration with image selection, image controls, sky/pixel information, FITS and sky context | Archive products remain explicit rows; catalogs/overlays aid inspection. This source does not establish a validated transient/motion candidate engine |
| ESASky [ESA overview](https://www.esa.int/About_Us/ESAC/Explore_the_cosmos_with_ESASky), [architecture paper](https://arxiv.org/abs/1610.09826) | Multi-mission discovery with sky context and simpler explorer access | Mission footprints/catalog context support follow-up; no VEGA-specific calibrated candidate evidence inferred |
| Aladin Lite [repository](https://github.com/cds-astro/aladin-lite) | Embeddable celestial survey viewer, HiPS sky context and catalog overlays; suitable celestial navigation | Epoch/candidate analysis is application logic, not automatic SPHEREx validation |
| WWT [WebGL SDK](https://docs.worldwidetelescope.org/webgl-reference/latest/), [documentation](https://docs.worldwidetelescope.org/) | Rich interactive celestial visualization and guided exploration | Tours can explain context, but the SDK does not establish VEGA photometry, detection or group readiness |
| NASA SkyView [fields](https://skyview.gsfc.nasa.gov/current/help/fields.html), [FAQ](https://skyview.gsfc.nasa.gov/current/help/faq.html) | Survey cutouts with target/position, projection and survey choices; distinguishes derived views from original survey resources | Catalog context is useful; reviewed material does not establish a general candidate assessment workflow |
| Backyard Worlds [research description](https://www.zooniverse.org/projects/marckuchner/backyard-worlds-planet-9/about/research) | Human inspection of processed infrared multi-epoch imagery | Blinking and artifact-aware inspection motivate evidence-first cards; apparent motion still needs follow-up, not automatic confirmation |
| IPAC Firefly [original repository](https://github.com/Caltech-IPAC/firefly) | Astronomy archive UI library with FITS/table/plot/HiPS scope | Strong alternative for richer archive interfaces; application still owns scientific inference and evidence interpretation |

| Reference | Adopt in VEGA | Exclude or defer | Reuse/license conclusion |
|---|---|---|---|
| IRSA/SPHEREx | Observation selection, persistent unit/identity, linked metadata/image inspection | Expert-control density in default Explorer | Inspiration only; no copied UI/assets/code and no assumption that NASA association licenses all components |
| ESASky | Simplified entry and contextual metadata | Multi-mission discovery scope in initial cutout workspace | No ESA code or design assets copied; exact component licensing not verified |
| Aladin Lite | Optional later sky-context panel | Mandatory science-pixel renderer: current native package grid/SIP mapping needs a verified adapter | Repository LICENSE fetched as LGPL-3.0; indexed documentation described GPL-3.0 and direct documentation URL returned 404. Freeze exact release/license before integration, retain required notices and assess redistribution/source obligations. No reuse now |
| WWT | Educational context as later enhancement | SDK/tour stack unnecessary for bounded cutout comparisons | SDK [license](https://raw.githubusercontent.com/WorldWideTelescope/wwt-webgl-engine/master/LICENSE) is MIT; imagery/data licenses are separate |
| SkyView | Clear survey/projection/derived-product labeling | External resampled cutouts as substitute for SPHEREx science pixels | No source/assets reused; license not established for intended reuse |
| Backyard Worlds | Paused blink, evidence inspection, artifact warnings | Human classification equals confirmed discovery; copying prepared imagery | Project UI/media permissions not established, no reuse |
| Firefly | Baseline alternative if future full FITS ecosystem is needed | Larger archive-stack integration without demonstrated need | License file not successfully established in this review; no code adopted. Deployment/integration cost is an assessment, not a benchmark |

Access limitations: the ESASky cosmos landing page and original SkyView help CGI were inaccessible; official alternate pages above were used. Aladin's direct doc URL failed; repository and retrieved license were used, with indexed-doc discrepancy retained explicitly. We did not claim to operate these interfaces interactively.

## Rendering technique comparison

| Technique | Scientific accuracy and WCS | Browser/large-data behavior | Backend/integration cost | Choice |
|---|---|---|---|---|
| Backend PNG + pan/zoom | Display-only quantization; original data/readout stay authoritative; WCS external | Simple decode; memory grows with raster dimensions | Render stretch and supply affine/readout | Baseline for small cutouts |
| PNG tile pyramid/DZI | Same display limitation; identical declared grid | Visible tiles load progressively | Tile generation/cache and stable transform | Optional above measured size threshold |
| Browser FITS + Canvas | Can retain raw arrays, but Canvas colors are not science values; SIP/masks need explicit implementation | Full-array transfer/memory/CPU; main-thread risk | FITS parser, numeric pipeline and validation | Defer until justified |
| Float textures + WebGL | Interactive stretch possible; numerical precision, masks and WCS remain responsibilities | GPU limits vary; context loss and texture size require fallback | Custom shaders/tested scientific mapping | Not baseline: no measured need |
| HiPS/Aladin | Natural celestial context and catalogs; resampling/grid may differ from cutout | Multi-resolution sky survey delivery | HiPS assets and native-grid bridge | Optional context, not authoritative science pixel plane |
| WWT SDK | Celestial exploration and narrative | Rich engine adds integration surface | SDK data adapter and imagery rights | Defer |
| Full Firefly stack | Astronomy-focused FITS/archive integration | Potentially broader than current bounded views | Integrate existing ecosystem rather than lean viewer | Alternative if scope expands |

These are qualitative assessments. No FPS, memory, bundle-size or browser compatibility numbers were measured. Benchmark with representative full-resolution products before setting production limits.

## Selected libraries, maintenance and licenses

- [OpenSeadragon repository](https://github.com/openseadragon/openseadragon) documents a zoomable image viewer; [tile creation guide](https://openseadragon.github.io/examples/creating-zooming-images/) establishes the need to prepare pyramids. Its [coordinate guide](https://openseadragon.github.io/examples/viewport-coordinates/) distinguishes screen, viewport and image coordinates; hence VEGA explicitly supplies a raster-to-science transform. [License](https://raw.githubusercontent.com/openseadragon/openseadragon/master/LICENSE.txt): BSD-3-Clause; preserve notices and conditions. It is selected for display, not celestial computation.
- [Plotly.js](https://github.com/plotly/plotly.js) is the selected optional chart library; [error-bar documentation](https://plotly.com/javascript/error-bars/) supports explicit uncertainty display. [Free/library licensing](https://plotly.com/javascript/is-plotly-free/) describes MIT for the open-source library. Commercial hosting products are separate. Lazy-load only needed trace types; no charts are fabricated before measurements exist.
- React/TypeScript is the proposed shell because tab/context/components need coordinated state. This is a project architecture choice, not an astronomy claim. React's [MIT license](https://raw.githubusercontent.com/facebook/react/main/LICENSE) requires notice preservation. Use direct lifecycle-managed OpenSeadragon integration rather than an unreviewed wrapper; optional [react-plotly.js](https://raw.githubusercontent.com/plotly/react-plotly.js/master/LICENSE) is MIT. A wrapper does not add WCS.
- [Astropy WCS](https://docs.astropy.org/en/stable/wcs/) provides FITS coordinate transformation with distortion support. Existing backend packages already use Astropy; full transformation remains there to avoid an unverified browser TAN-SIP approximation.

Repositories/documentation for OSD, Plotly, React and WWT were accessible at review time. This is evidence of available upstream resources, not a support SLA or independently measured maintenance cadence. No npm dependency was installed or pinned during this specification task. At implementation freeze exact versions, inspect their own LICENSE/dependencies, preserve notices, record a lockfile/SBOM, and run browser/WCS integration checks. License observations describe fetched artifacts, not legal advice or blanket permission for sky imagery.

## Scientific visualization findings and selected behavior

SPHEREx [data products](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/) and [introductory tutorial](https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/) anchor product interpretation: image intensity, flags, spectral response/calibration and extensions have distinct roles. Display maps cannot replace calibrated spectral work. The existing packages retain IMAGE, VARIANCE, FLAGS, masks, celestial WCS and EPSF. No frontend spectral inference is introduced.

Chosen implementation requirements: native-grid preview plus authoritative backend readout; transparent invalid pixels with independent masks; backend-projected source overlay; explicit ICRS coordinate labeling; metadata timeline before science comparisons; paused visual-only blink and side-by-side; difference only from delivered authorized results; motion tracks only with timed associations; evidence cards with method/version/uncertainty; persistent provenance and warnings. Their detailed thresholds/layout are VEGA policy, not requirements attributed to external projects.

## Project evidence and risks

Inspected first package c40a0dfa-5780-48d5-bea2-ff235c0274c2/sky_visualization metadata: request c7fe7b2a-55b0-48dc-bcfe-ffdc3853fb70, product ivo://irsa.ipac/spherex_dr1?2025W19_2B_0101_1/D3, observation 2025W19_2B_0101_1, version 7.0.5, native 59×58 arrays, ICRS TAN-SIP, units originally MJy / sr and MJy2 / sr2. Metadata and linked reports, rather than user prose alone, informed decisions. No original file was changed, no FITS downloaded and none of these real products was relabeled as a mock detection.

Risks: missing result_formatter/API/rendered assets; unexecuted algorithms and conditional/blocked readiness; unassessed group compatibility; data-dependent spectral calibration; handling RA wrap/poles and SIP; unknown browser limits; separate data/software licenses; schema checks cannot prove scientific provenance. Mitigations and acceptance checks are explicit in the handoff. Research is complete enough to build presentation in mock mode, not evidence of an operational scientific web service.
