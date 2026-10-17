# Batch 21 — Market intelligence exchange corpus and import (1 component)

Baseline main `3caefe090dfe4b71ebd8eab16a2f2811ad6b5cd7`. Complete source review of `backend/src/jolt/market_intelligence_exchange.py` with read-through of `market_intelligence_view.py` and `market_intelligence_observations.py` as supporting dependencies (these were previously counted). Static only.

**MI-01 Medium — evidence window semantics.** `_posting_evidence` uses a 90-day period and a 500-row **observation** limit, not 500 distinct jobs; repeat observations can consume quota. The returned authority notes expressly warn about this. Test representative repeated captures and verify whether 500 newest observations is appropriate for the intended market question.

**MI-02 Medium — incomplete status exclusion.** `_posting_evidence` excludes runs marked `running` but does not itself require `completed`. A failed or partial run can contribute verified items. This might be deliberate retention of reliable evidence despite partial batch failures; check actual run states and status labels before changing.

**MI-03 Medium — limited matching guarantees.** Join against CaptureRun, SourceDocument and Posting with `CaptureItem.detail_status == verified`; does not itself enforce a separate employment-eligibility decision. The authority notes correctly state listing country is not eligibility. Review downstream UI labels for clarity.

**MI-04 Medium — legacy persistence.** `import_market_intelligence_exchange` validates section and rejects section context patches, but then calls `save_ai_exchange_feedback`. Thus this deprecated import saves feedback independently from unified package operation. Verify idempotency and consistency after errors; do not disable until callers/tests are inventoried.

**Positive:** explicit corpus policy, SHA-256 evidence reference and source-first exclusion of local evaluation scores; context patches rejected in this path. No code/data changes.

**Cumulative coverage:** 144/333 = 43.24%, 189 pending, subject to exact-head checks and merge.
