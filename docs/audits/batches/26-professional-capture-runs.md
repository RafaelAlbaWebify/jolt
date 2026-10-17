# Batch 26 — Professional capture-run state machine (1 component)

Baseline main `031edd7e370b8048dbda8deed44eddd4e44effa4`. Entire `backend/src/jolt/professional_intelligence_capture_runs.py` read with model and API routing dependencies.

- **PI-23 High reliability:** `recover_stale_professional_capture_runs` determines stale state from `started_at`, rather than the existing `progress_updated_at` heartbeat. A legitimately long run with active progress may be set to `interrupted` after 30 minutes when listing/retrieving captures; check live worker heartbeat and add disposable long-running regression test before changing.
- **PI-24 Medium side effect:** read/list functions call recovery and may commit DB changes as part of GET; distinguish deliberate recovery from observational API.
- **PI-25 Medium performance:** `list_professional_capture_runs` materializes entire history and `_to_response` executes artifact-count query for each, an N+1 pattern. Confirm scale before aggregation optimization.
- **PI-26 Medium status authority:** authorization expiry is computed dynamically by `effective_capture_run_status`, but stored status may remain `authorized`; persistence/history semantics and restart cleanup should be tested.
- **Positive:** explicit bounded capture options, immutable source snapshot, authorization phrase/user presence, cancellation flag for running captures, career-source prioritization and 15-minute authorization limit.

Static evidence only. **Coverage 164/333 = 49.25%, 169 pending**; no production or user-data changes.
