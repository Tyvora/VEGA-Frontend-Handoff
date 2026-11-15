# VEGA — Frontend Research & Handoff

Public developer handoff for Sky Viewer, Timeline and Discoveries.

**Start here: [FRONTEND_HANDOFF.md](backend/Scientific_Analysis_Engine/frontend_contracts/FRONTEND_HANDOFF.md).**

This repository includes UX specifications, official-source research, design decisions, four JSON Schemas (Draft 2020-12), eighteen synthetic mock responses, a labeled SVG fixture, and offline contract tests. Selected upstream pipeline READMEs are included so the handoff references remain readable; pipeline implementation and scientific datasets are not included.

No frontend app, backend API, Result Formatter or scientific algorithm is implemented here. All mock candidates and evidence are synthetic and must not be presented as NASA observations or validated discoveries.

## Check contracts

```sh
python -m pip install -r requirements-dev.txt
cd backend/Scientific_Analysis_Engine
python -m pytest -p no:cacheprovider tests -q
```

## Serve static fixtures

```sh
cd backend/Scientific_Analysis_Engine/frontend_contracts
python -m http.server 8000 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8000/sky_viewer/example.mock.json`. This is a static fixture server, not an application or scientific API.

The handoff records technical choices, licensing observations, current scientific limitations, proposed API operations and frontend acceptance criteria. Original source references remain attributed in the research report. Public visibility does not itself grant a software license; no license for the owner's original materials is assigned by this upload.
