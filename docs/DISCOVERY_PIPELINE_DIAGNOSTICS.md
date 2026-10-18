# JOLT Discovery Pipeline — Targeted Architecture Diagnosis

This is a **source-only diagnostic**, not proof that a portal works live.

## Run from repository root

```powershell
python .\tools\diagnose_discovery_pipeline.py --output "$HOME\Downloads\JOLT_DISCOVERY_ARCHITECTURE.json"
```

The script reads Git-tracked files and parses Python imports. It **does not** call JOLT APIs, touch SQLite, open browsers or perform captures. Its default output is `.jolt/diagnostics/discovery-architecture.json` (ignored runtime data). Run the regression tests from `backend` with `uv run pytest tests/test_discovery_diagnostics.py`; other CI jobs may provide broader coverage.

## Interpreting the JSON

- `portal_inventory`: named source files, source-named tests and static import paths from portal modules to shared ingestion/index/database modules. The absence of a named module is **not** proof that the portal is unimplemented.
- `stage_modules` and `entrypoints`: heuristic candidate sets to prioritize manual source tracing.
- `modules`: parsed top-level definitions, direct imports, and keyword signals. A keyword signal is **not** a verified behavior.
- `parse_errors`: malformed or unreadable tracked Python files; nonzero exit on any errors.
- `unverified_questions`: issues this static runner cannot settle.

## What requires a second phase

Real portal captures must be executed in the operator's authenticated Windows session, bounded by an explicit per-source job limit, using a **disposable or approved database**. Evidence needs a source URL, full verified description, saved-search ID, capture run ID, duplicate decision, ingestion outcome and the record's visibility in Review Inbox. Measure operator interventions and elapsed time independently.

A PASS for this script only means the static inventory completed without parse errors. It does **not** mean InfoJobs, Jobgether, Indeed or LinkedIn works. Do not treat this run as a readiness gate for production rollout.

## Audit plan: smallest useful evidence

1. Identify the actual entrypoint for each portal with `portal_inventory`; trace to the shared capture schema and ingestion path. Escalate missing edges for manual resolution, including dynamic imports and frontend HTTP calls.
2. For the failing portal, reproduce a known error in an isolated fixture and add a targeted test for its root cause.
3. Validate its bounded end-to-end path (saved search → capture → source evidence → database → Review Inbox) without touching live user data.
4. Record a dated PASS/FAIL and time saved; stop expanding architecture audit unless a specific failing dependency requires it.

The 300-file historical audit register is not a target for this process.
