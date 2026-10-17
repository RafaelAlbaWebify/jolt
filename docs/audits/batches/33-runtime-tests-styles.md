# Batch 33 — Runtime identity, AI status, contact and application-card tests plus styling (5 components)

Baseline main `a1481ee131f6305d20dd8ebf4a547a7904cdc906`. Five full source reads; test review is not test execution.

| File | Finding |
|---|---|
| `frontend/src/RuntimeIdentity.test.tsx` | **TEST-09 Medium:** validates matching and mismatched backend commit display plus diagnostics, but lacks unavailable API/network failures, invalid metadata and delayed response ordering. Good explicit stale-runtime warning coverage. |
| `frontend/src/LinkedInAIAnalysisStatus.test.tsx` | **TEST-10 Medium:** covers stale and current statuses; no `no_evidence`, `not_analyzed`, failure, or mid-fetch activation changes despite fixture type supporting states. Add exhaustive backend-status contract assertions. |
| `frontend/src/ApplicationContacts.test.tsx` | **TEST-11 Medium:** edit/cancel/retry happy/error paths covered, but no A-to-B application switch while A request is unresolved or changing onError identity while editing; missing regression for FE-20/21. |
| `frontend/src/ApplicationCardSignals.test.tsx` | **TEST-12 Low/Medium:** only overdue=true fixture, no missing timestamps, timezone boundary, document unavailable or status transitions; validates visual labels but not temporal correctness. |
| `frontend/src/ProfessionalIntelligence.css` | **STYLE-04 Low:** CSS retains many rules for previously moved professional-source/editor/evidence controls, while current `ProfessionalIntelligence.tsx` primarily renders Capture Jobs; inventory potentially unused selectors before removing. A few literal light-theme colors remain in destructive and advanced fallback states; verify contrast/visual screenshots. Responsive 900px layout and overflow wrapping are positive. |

Coverage proposed **196 / 333 = 58.86%**, 137 pending. Findings static, no code changes.
