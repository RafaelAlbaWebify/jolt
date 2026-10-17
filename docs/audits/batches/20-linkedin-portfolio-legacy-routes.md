# Batch 20 — LinkedIn portfolio router and legacy exchange APIs (3 components)

Baseline: main `3caefe090dfe4b71ebd8eab16a2f2811ad6b5cd7`. Three entire source modules reviewed; no authenticated operator runtime or database access.

| Component | Findings |
|---|---|
| `backend/src/jolt/linkedin_search_portfolio_api.py` | **API-01 Medium:** `_run_discovery_batch_background` catches all failures, rolls back, attempts failure recording, and closes the session; if `mark_discovery_batch_background_failure` itself raises, error reporting and stable terminal state are not guaranteed. Check exception-to-terminal-state contract and restart reconciliation. **API-02 Medium:** FastAPI `BackgroundTasks` is an in-process execution mechanism, not a durable job queue; pending work depends on startup recovery, which must be verified with real restart scenarios. **API-03 Low:** deprecated AI review export/import remain active; migrate consumers only after backward-compatibility assessment. Explicit path/body batch-ID check is a positive guard. |
| `backend/src/jolt/market_intelligence_exchange_api.py` | **LG-04 Medium:** deprecated `/api/ai-market/import` still calls `import_market_intelligence_exchange`, rather than failing closed like global context import; verify inclusion, writer semantics, consistency with unified atomic import and downstream consumers. `/view` is nondeprecated; must not be removed as legacy by association. |
| `backend/src/jolt/linkedin_profile_exchange_api.py` | **LG-05 Medium:** deprecated `/api/ai-linkedin/import` remains a working writer through `import_linkedin_profile_exchange(session, output)`. Verify full validation, idempotency, transaction boundaries, and whether unified import alone is intended. Error mapping 404/400 is explicit; deprecation does not disable the path. |

**Cross-component:** three separately reachable legacy import surfaces now documented alongside data-quality import, while global-context import returns 409. Do not assume uniform deprecation behavior. Preserve historical reviews and live records before any consolidation.

Coverage: **143 / 333 = 42.94%**, 190 pending. Source audit only; no functional acceptance implied.
