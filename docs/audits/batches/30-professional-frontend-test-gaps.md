# Batch 30 — Five professional frontend test modules

Baseline main `a1481ee131f6305d20dd8ebf4a547a7904cdc906`. Complete source review of five test files and corresponding production components (previous batches 28–29). These are **test quality findings**, not claims that tests fail; no tests executed here.

| Test file | Scope and uncovered risk |
|---|---|
| `frontend/src/ProfessionalCapturePlan.test.tsx` | **TEST-01 Medium:** covers activation and baseline happy-path rendering only. Does not exercise `StrictMode` effect replay, rejected request, refreshKey transitions or out-of-order responses—the failure modes identified in FE-13. |
| `frontend/src/ProfessionalEvidenceRoot.test.tsx` | **TEST-02 Medium:** verifies initial GET and successful POST to configured folder but lacks concurrent GET/POST race, slow response, failed configuration, and unsaved input preservation tests (FE-09). |
| `frontend/src/ProfessionalEvidenceReview.test.tsx` | **TEST-03 Medium:** only success fixture with valid artifacts; no modified hash, missing artifact, partial source, changed runId or stale fetch tests (FE-15). |
| `frontend/src/ProfessionalCaptureRuns.test.tsx` | **TEST-04 High drift risk:** fixture `ROUTING_SUMMARY` assigns `job_opportunities:1`, career target bucket `job_opportunity` and `routing_status:needs_canonical_ingestion`; current backend `professional_intelligence_routing_summary.py` classifies career pages as `market_signal`, with status `needs_review`. Mock-only UI tests can validate an impossible contract and conceal integration drift. **TEST-05 Medium:** tests single-run import, profile-only restriction and login retry, but not multi-run map preservation, 2-second polling races, failures, deletion or partial-job verification (FE-16–19). |
| `frontend/src/ProfessionalStructuredExtraction.test.tsx` | **TEST-06 Medium:** demonstrates term/source snippet rendering but no failed integrity, run change, false substring match or stale result test (FE-11–12/PI-21). |

**Action:** align capture-run fixture with true backend contract; add contract or API-driven tests and adversarial concurrent-response cases before attributing stability to unit test success.

**Cumulative proposed coverage:** 183/333 = 54.95%, 150 pending. Source inspection complete; CI/merge still required.
