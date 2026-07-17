# Capture pagination follow-ups

PR #49 adds bounded multi-page LinkedIn capture, real page provenance, retry handling, and search-state evidence.

## Completed integrity validation

The live-capture request now validates these invariants at the Pydantic request boundary so malformed input returns HTTP 422 before persistence:

- page numbers are unique;
- page numbers are contiguous and begin at 1;
- `next_control_enabled=true` requires `next_control_present=true`;
- live item job IDs are unique within a request;
- when page evidence is supplied, every submitted item job ID appears in at least one observed page;
- visible job IDs are normalized, non-empty, and deduplicated within each page.

Requests that omit optional page evidence remain backward compatible and continue to use the existing synthetic single-page fallback during persistence.

## Architecture cleanup

The current Windows runner uses `capture_runtime_enhancements` as a compatibility layer around `multipage_capture`. After CI execution is restored, fold the validated behavior into the primary multi-page module and remove runtime monkey-patching. Preserve the existing public PowerShell contract and the Windows console-input workaround.

## Required validation

Run Ruff, Ruff format, Pyright, pytest, PowerShell parsing/contract checks, and one bounded Windows capture before merging PR #49 or beginning the compatibility-layer cleanup.