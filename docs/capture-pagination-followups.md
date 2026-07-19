# Capture pagination follow-ups

PR #49 added bounded multi-page LinkedIn capture, real page provenance, retry handling, and search-state evidence.

## Completed integrity validation

The live-capture request validates these invariants at the Pydantic request boundary so malformed input returns HTTP 422 before persistence:

- page numbers are unique;
- page numbers are contiguous and begin at 1;
- `next_control_enabled=true` requires `next_control_present=true`;
- live item job IDs are unique within a request;
- when page evidence is supplied, every submitted item job ID appears in at least one observed page;
- visible job IDs are normalized, non-empty, and deduplicated within each page.

Requests that omit optional page evidence remain backward compatible and continue to use the existing synthetic single-page fallback during persistence.

## Architecture cleanup

Issue #53 replaces the temporary `capture_runtime_enhancements` compatibility layer with explicit orchestration in `linkedin_capture`:

- `multipage_capture` retains bounded pagination and low-level LinkedIn DOM helpers;
- `linkedin_capture` owns one capture session, retry metrics, search-state evidence, API submission, diagnostics, and one-pass packaging;
- the Windows console wrapper installs the existing console-input workaround and calls `linkedin_capture.main()` directly;
- page evidence is passed explicitly rather than stored in process globals;
- capture ZIPs are complete before their first and only packaging pass;
- no runtime assignment replaces functions in another module.

The compatibility layer can be removed once the regression suite and one bounded Windows capture prove the new orchestration path.

## Required validation

Run Ruff, Ruff format, Pyright, full pytest, PowerShell parsing and contract checks, one bounded supervised Windows capture, and final Windows certification before merging issue #53.
