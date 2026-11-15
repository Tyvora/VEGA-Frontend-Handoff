# Data Pipeline Orchestrator

`run_pipeline` coordinates the nine existing public stage APIs; no science algorithm is executed. Flow: User Input -> Request Validation -> Archive Search -> explicit Observation Selection -> Data Download -> FITS Extraction -> Technical Validation -> Scientific Quality Validation -> Analysis Readiness -> Algorithm Inputs. Selection is coordination, not a new scientific stage. No previous stage code or shared contract was changed.

## One-call usage

From Data_Preparation_Pipeline, with known explicitly chosen product IDs:

```python
from orchestrator import run_pipeline, WorkflowLimits
workflow, manifest = run_pipeline(
 ['ivo://irsa.ipac/spherex_dr1?2025W19_2B_0101_1/D3'],
 method='coordinates', value={'ra':210.80227, 'dec':54.34895},
 goal='sky_viewer', fov_deg=0.1,
 limits=WorkflowLimits(max_products=1))
```

Names/presets are passed to the public User Input API in the same way. A new request runs public SIA2 archive search and saves the request, accepted report and search results. Product selection is always explicit and must identify exactly one downloadable catalog row. No default downloads the full catalog. A missing/ambiguous/ineligible selected product fails selection; there is no arbitrary fallback to another product. Product IDs are kept separate from observation IDs, observation times and detector labels.

To use a saved normalized request and verified prior SIA2 search, pass request_file and cached_search. The search Request ID must match, and every recorded POS circle must agree with accepted RA/Dec/FOV. No cached search is reassigned to a different request. Input Contract is enforced by the public validation stage. The two other shared contract files are still empty; the orchestrator does not invent semantics for them.

## Recovery and reuse

```python
workflow, manifest = run_pipeline(resume=manifest)
```

A Run ID and a mutable atomic workflow-<UUID>.json live in data/manifests. Resume preserves run/request/selection/limits, rejects changed source references or selection, and rechecks content hashes. Each stage has pending/running/completed/partial/failed/skipped, start/end, input/output references, warnings/errors, input signature, output size/SHA-256 and previous-attempt history. Completed/partial output reuse requires a matching input signature and intact recorded files; file existence alone is insufficient. Running/failed stages rerun. A reused stage retains original execution timestamps and adds reuse_verified_at; imported preexisting artifacts are explicitly marked reused_from_existing. Historical errors are retained separately from current errors. Packages are reread with the public package reader, including its external references and readiness gates.

Existing valid downloads are discovered in download manifests only when request/product/observation/collection/source URL/mode/cutout geometry/hash/size agree. Corrupt/different-request downloads are not reused. `reuse_packages={product_id: preparation_report_path}` explicitly imports a full prior chain: every public Package Reader must verify it, and its exact extraction/technical/quality/readiness references must link to the same downloaded source. This allows the existing M101 chain to be reused without re-extraction. If an explicitly supplied bundle is invalid, the product fails preflight rather than silently attaching it to a different request. Other products continue. Resume does not automatically overwrite or repair older artifacts; rerun stages create new upstream outputs and downstream signatures change accordingly.

This version is a single-writer runner: do not concurrently resume the same workflow manifest from multiple processes. Atomic replacement prevents torn checkpoints, not concurrent-writer races. Kill/KeyboardInterrupt leaves a recoverable running record; exception failures are recorded and downstream stages are skipped for that product. If a stage generated a failed report, its reference is retained where returned by the adapter. Earlier run histories produced before that enhancement may contain only the original error message.

## Limits and statuses

WorkflowLimits defaults: one explicitly selected product, 32 MiB/file, 64 MiB total download payload budget, 300 seconds per invocation, 60-second read timeout, zero download retries. The three-product experiment explicitly enabled max_products=3. Downloads are sequential cutouts only; there is no full-file fallback. Every download uses the public stage's limits and cancellation callback. Remaining payload budget is passed into that stage. Reservations are persisted before network traffic; on a normal return, actual recorded bytes replace the reservation. A hard interruption may leave a conservative reservation charged even if exact transferred bytes are unknown, avoiding an accidental unlimited budget reset. network_bytes_recorded is confirmed payload, not HTTP/TLS overhead. Limits remain fixed on resume. Each explicit resume starts a new bounded wall-clock invocation while preserving the cumulative payload charge.

Time is checked before stage execution and between download chunks. This is a cooperative wall-clock budget, not preemptive process cancellation: an in-flight network read can finish at its bounded read timeout, and a CPU stage is allowed to return. Existing public stage APIs do not expose universal cancellation. SIA requests are individually bounded (no unbounded fallback TAP query). There is no daemon or background scheduler.

Workflow completed means all explicitly selected products reached packages, not that every archive product was processed or every scientific capability is ready. Archive partial status and warnings remain in the stage; explicit selection from partial results is permitted, never presented as full archive completeness. A mixture of successful/failed products yields partial; no successful product yields failed. Package references are cleared for a product that fails revalidation.

## Readiness

Each prepared product is evaluated independently through the public readiness API, and its capability decisions are copied unchanged into the manifest. Package preparation follows those decisions. Source detection/photometry conditional does not authorize scientific execution; blocked background/temporal/spectral packages are not created. No algorithm is called. Multiple successful products do not promote temporal readiness. The readiness API does support multiple InputReferences, but this runner deliberately records group_temporal_readiness=not_evaluated and does not merge individual reports into a group decision. A future explicit group evaluation must verify independent exposures, spectral responses, registration and calibration; same detector name alone is not proof of comparability.

## Real verification

Single existing M101 product: workflow-4339c5d6-6562-418f-a1ab-6c56cf02b00a.json completed 1/1 with zero network payload. The original normalized request was not previously persisted; the live setup reconstructed its known geometry from the saved POS/report and session's original sky_viewer input, retained the existing Request ID, validated it, and saved data/requests/c7fe7b2a-55b0-48dc-bcfe-ffdc3853fb70.json. This is disclosed recovery of the earlier record, not a claim that an original request file existed. Automatic production runs persist new requests immediately.

Three selected DR1/D3 products: observation IDs 2025W19_2B_0101_1, _2, _3 with nonoverlapping documented MJD intervals [60804.148555,60804.149887], [60804.150047,60804.151379], [60804.151539,60804.152871]. This is evidence of separate recorded exposures, not a validated temporal comparison. Workflow workflow-6f6147ef-06b0-452f-9f74-968153db845b.json initially completed 2/3 after IRSA returned HTTP 503 for the second product. A single explicit resume retried only that failure and completed 3/3. Confirmed new payload total 8167680 bytes (two cutouts); first product and completed third product were reused during recovery. All packages were successfully read. No additional observations were invented or downloaded for temporal analysis.

Final package runs: existing c40a0dfa-5780-48d5-bea2-ff235c0274c2; new 670a089b-984e-406a-a3d8-e48a7f997196 (second observation), dfe4b0c7-2493-4eb0-b328-dcce3def332e (third). Each has sky_visualization, source_detection and photometry directories; their original gates remain enforced. Processing reports for extraction/technical/quality/readiness are referenced by the workflow manifest.

`python -m orchestrator.live_verify` reruns the bounded three-product demonstration; it should not be used as a production scheduler. `python -m pytest -p no:cacheprovider tests` runs the full offline regression suite. New tests cover one-call mocked interfaces, one/multiple products, isolated mid-pipeline failure, interrupted resume without redownload, corrupted output rejection, request/selection/reference isolation, payload/time limits, real existing M101 reuse, package reading and unchanged readiness gates. Live IRSA success is documented separately from mocked tests.
