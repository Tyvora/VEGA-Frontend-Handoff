# User input

`create_request(method, value, goal, fov_deg=None, resolver=None)` creates a request ready for request validation or marks name resolution pending. Methods: `coordinates` takes `{"ra": 279.2347, "dec": 38.7837}` (numeric degrees) or explicit sexagesimal strings (`18h36m56.3s`, `+38°47′01″`); `preset` takes `m31`; `name` takes a catalog designation. Astropy interprets coordinates in ICRS. Goals: `sky_viewer`, `timeline`, `discoveries`. `save_request(request, directory)` writes a UUID-named JSON file exclusively; pass the pipeline's `data/requests` directory.

FOV is the circular angular **diameter**, in degrees. The application default is 0.1 degrees, not a NASA limit. Positive user values are accepted; operational bounds belong to request validation. Presets include a version and reference. Coordinates are catalog positions, not predictions for an observation date.

`SesameResolver(cache_dir=..., timeout=5, retries=1, endpoint=0)` uses CDS Sesame, with the documented IDIA mirror selectable by endpoint=1. Names are encoded as query data. `force_refresh=True` bypasses cache. If no cache directory is provided, the local cache is used. Successful responses expire in seven days, not-found and ambiguous responses in one hour; failures are not cached and expired data are not used offline. Sesame may not supply multiple candidates; ambiguity cannot always be detected. Exact planet names are rejected, but arbitrary moving object designations cannot reliably be classified. Resolved positions do not establish accuracy at a different epoch.

Run from `Data_Preparation_Pipeline`: `python -m pytest tests/unit/test_user_input.py`. Requires Astropy, pytest, and jsonschema. Reference: https://tapvizier.cds.unistra.fr/vizier/doc/sesame.htx ; https://docs.astropy.org/en/stable/coordinates/ ; https://ned.ipac.caltech.edu/byname?objname=M31 .

## Resolver and cache details

The default cache is `user_input/cache/` and is created on first cacheable result. The key incorporates normalized name, endpoint and rules version. Records include the original query, source, retrieval and expiry times. Resolved results live seven days; confirmed `NNNothing found` and ambiguous results live one hour. Connection and parser failures are not cached; expired results are never used as fallback. `force_refresh=True` bypasses local cache. Sesame requests include `~` to bypass the service cache. Cache write failures do not stop resolution. Cache contents are operational data, not scientific products.

A result requires a matching echoed name, a source, canonical designation and finite valid coordinates. The Sesame documented response with multiple resolver entries is surfaced as ambiguous; its default first-match behavior does not prove there are no other candidates. Only explicit `NNNothing found` is classified as not found; empty or incomplete replies are resolver errors. Timeouts and server failures are service unavailable. Exact solar system names are rejected; other moving objects cannot be reliably classified. J2000 positions are not propagated to an observing epoch. The M31 preset is a catalog-position approximation and the chosen diameter is an application default.

Run all tests from the pipeline directory with `python -m pytest tests`. The JSON Schema checks the structure and relationships but is not the final scientific or operational validation. Resolver live calls are separate from mocked tests.

