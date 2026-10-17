# Batch 19 — Saved-search performance and legacy market export (2 components)

Baseline: main `3caefe090dfe4b71ebd8eab16a2f2811ad6b5cd7`. Complete static file review; runtime verification not performed.

| Component | Findings |
|---|---|
| `backend/src/jolt/linkedin_search_performance.py` | **LP-01 Medium (scaling):** `build_linkedin_search_performance` loops each saved search and queries discovery runs, CaptureItem posting IDs, latest AI/human decisions, applications, events and outcomes separately, producing multi-query amplification per search. Prefer grouped materialization/aggregation if profiling confirms a bottleneck. **LP-02 Medium (metric semantics):** summed run-level `captured_count` and `verified_count` measure cumulative observations; `canonical_posting_count` counts distinct linked Postings. Dashboard must label both distinctly. **LP-03 Medium (outcomes history):** `outcomes_by_application` overwrites same-application outcomes without ordering; acceptance count may depend on arbitrary row selection if multiple outcomes exist. Test a multiple-outcome application and decide authoritative final outcome. **LP-04 Low/Medium:** reached-stage counts include historical progress, not necessarily current application status; explicitly label as ever reached and test transitions. |
| `backend/src/jolt/market_preparation_pack.py` | **LG-03 Low:** compatibility-only archive explicitly points to unified AI work package and excludes local evaluation scores; good source-first safeguard. **EX-04 Low:** entire exchange serialized to bytes and zipped in memory; potential scaling issue if datasets grow. Verify callers and deprecation usage before removal. SHA-256 manifest provides integrity metadata, not confidential transport. |

All issues are static observations. No code, user data or running processes modified. **Coverage 140/333 = 42.04%, 193 remaining**, conditional on CI and merge.
