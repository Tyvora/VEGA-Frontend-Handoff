# VEGA frontend contracts 1.0.0

Start with [FRONTEND_HANDOFF](FRONTEND_HANDOFF.md). This directory is a developer specification, not a running frontend or API.

- [Research and sources](RESEARCH_REPORT.md)
- [Decision records](DESIGN_DECISIONS.md)
- [Sky Viewer](sky_viewer/README.md), [Timeline](timeline/README.md), [Discoveries](discoveries/README.md)
- [Shared states](shared/states.md), [proposed API](shared/API_PROPOSAL.md), [algorithm traceability](shared/TRACEABILITY.md)
- Shared Draft 2020-12 definitions: [common.schema.json](shared/common.schema.json). Each view has response.schema.json and six *.mock.json fixtures.

All fixtures are synthetic, prominently labeled, and use a locally generated SVG containing MOCK — NOT SKY DATA. No scientific detection, confidence estimate, calibrated measurement, API service or browser application is supplied.

From backend/Scientific_Analysis_Engine run `python -m pytest -p no:cacheprovider tests`. No virtual environment is required. Tests need pytest, jsonschema and referencing. See the handoff for local static fixture serving.

Machine-readable acceptance evidence and scope-integrity hashes: [DELIVERY_VERIFICATION.json](DELIVERY_VERIFICATION.json).
