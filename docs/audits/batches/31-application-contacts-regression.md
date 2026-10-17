# Batch 31 — Application contacts and frontend regression tests (4 components)

Source baseline main `a1481ee131f6305d20dd8ebf4a547a7904cdc906`. Four complete source files reviewed against existing application UI and professional-capture modules. Findings below are static; no test suite executed.

| Component | Finding |
|---|---|
| `frontend/src/ApplicationContacts.tsx` | **FE-20 Medium:** `load()` has no cancellation or response-order protection. Reusing the component with a new `applicationId` while the prior fetch is unresolved can display contacts belonging to the previous application; contact management contains personal data, so source mismatch needs a regression test. **FE-21 Medium:** effect dependencies include `onError` through `load`; if the parent passes a non-memoized callback, re-renders can retrigger GET and reset an in-progress contact draft. **FE-22 Medium:** persisted contact `linkedin_url` is used directly in an external anchor; ensure server validates HTTPS and LinkedIn origin before display. **Positive:** edit/add require explicit user action, read-only disables writes, links use `rel=noreferrer`. |
| `frontend/src/ReadinessHistory.test.tsx` | **TEST-07 Medium:** covers only happy-path refresh and history rendering; no failed API, rapid posting switch, or stale-response ordering test. Does not reproduce potential FE-06 race. |
| `frontend/src/ProfessionalIntelligence.test.tsx` | **TEST-08 Medium:** mocks both LinkedIn capture subcomponents, asserting headings/visibility rather than integration between queue, capture, and Review Inbox. Good smoke coverage of navigation boundaries, not end-to-end capture proof. |
| `frontend/src/ProfessionalIntelligence.tsx` | **FE-23 Low/Medium:** always mounts discovery queue and capture-history even when inactive (passing active through), while advanced capture and LinkedIn portfolio are rendered in collapsed `details` and may still mount children; confirm their fetch effects honor `active` and avoid unnecessary requests. **Positive:** separates multi-portal discovery workflow from legacy advanced LinkedIn controls, with explicit read-only language. |

Suggested tests: contact A/B race with deferred fetch, rerender with changing onError identity while editing, malicious/malformed LinkedIn URL, and a nonmocked cross-workspace integration scenario. Review does not assert a working exploit.

Cumulative proposed coverage **187 / 333 = 56.16%**; **146 pending**.
