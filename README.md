# VEGA_BESTPROJECT

Public source snapshot of the VEGA project: the complete existing Data Preparation Pipeline source, tests and documentation; Scientific Analysis Engine scaffolding; and Frontend Handoff contracts/specifications.

**Frontend developer: start with [FRONTEND_HANDOFF.md](backend/Scientific_Analysis_Engine/frontend_contracts/FRONTEND_HANDOFF.md).**

## Included

- All nine existing Data Preparation Pipeline stages and its orchestrator, schemas, tests, and READMEs.
- Scientific Analysis Engine directory structure and existing documentation. Empty algorithm folders are scaffolding, not implemented algorithms.
- Frontend research, UX specifications, decisions, four JSON Schemas (Draft 2020-12), eighteen synthetic mock responses, a labeled SVG fixture, and offline contract tests.
- Original empty placeholder contracts are retained as empty files.

## Deliberately excluded

Scientific datasets (FITS/NPZ/NPY), observation products, prepared packages, processing reports/manifests/search results, diagnostic live_probe.json, local caches and virtual environments are excluded. Data storage directories are represented with empty .gitkeep files; these do not contain data. .gitkeep also preserves empty code directories because Git does not track empty directories. See [PUBLICATION_AUDIT.json](PUBLICATION_AUDIT.json) for source file inventory and integrity hashes. Original Desktop project files were not modified.

No frontend app, backend API, Result Formatter or scientific analysis algorithm is implemented in this source snapshot. Synthetic examples must never be presented as NASA observations or validated discoveries.

## Dependencies and tests

```sh
python -m pip install -r requirements-dev.txt
cd backend/Scientific_Analysis_Engine
python -m pytest -p no:cacheprovider tests -q
```

The dependency pins record the available publication interpreter's installed versions; select a compatible Python for those versions. Frontend contract acceptance: 143 passed in the publication check.

Pipeline tests run from backend/Data_Preparation_Pipeline with `python -m pytest -p no:cacheprovider tests`. Some existing tests require the deliberately excluded real M101 files, so the full suite cannot pass on a data-free checkout without restoring those inputs and their verified references. All such tests are retained unchanged; their absence of data is not reported as a scientific validation success. Source compilation and frontend contract validation can be checked without real observations. Scripts named live_* or probe/verify are explicit network/data operations and are not needed to read this handoff.

## Static frontend fixtures

```sh
cd backend/Scientific_Analysis_Engine/frontend_contracts
python -m http.server 8000 --bind 127.0.0.1
```

Open http://127.0.0.1:8000/sky_viewer/example.mock.json. This serves static fixtures, not an application or scientific API.

Public visibility does not itself grant a software license; this upload assigns no new license to the owner's original materials. Upstream research and software license observations remain attributed in the research report.
