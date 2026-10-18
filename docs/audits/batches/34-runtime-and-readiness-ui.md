# Batch 34 — Runtime diagnostic, AI status, evidence readiness and archived resources (5 files)

Baseline `main` merge `f34749746a48c509b1f3c0cc07a8d3b49a1c606a`. Complete source reads, direct UI contracts compared with earlier reviewed modules. No tests executed. Distinguish demonstrated code behavior from runtime hypotheses.

| File | Finding |
|---|---|
| `frontend/src/RuntimeIdentity.tsx` | **FE-24 Medium:** developer diagnostics `loadIdentity()` lacks a cancellation/request-ID guard. An older response may overwrite a newer manual retry or changed `apiBase` identity; staleness guard correctly has a cancellation flag. **FE-25 Low:** guard intentionally remains silent on fetch failure, so unverified state must not be interpreted as positive freshness. |
| `frontend/src/LinkedInAIAnalysisStatus.tsx` | **FE-26 Medium:** while a new fetch is pending, the prior status remains displayed; a change in `apiBase` or `importRevision` can temporarily advertise current/stale state from previous snapshot. The effect correctly ignores results after cleanup. Error display is explicit. |
| `frontend/src/ApplicationReadiness.tsx` | **FE-27 Low:** rows use the item string as React key, so duplicate evidence bullets can trigger duplicate-key warnings and unstable reconciliation. No content mutation; clear separation of evidence, warnings, revision topics and checklist. |
| `frontend/src/OpportunityApplicationHandoff.tsx` | **FE-28 Medium truthfulness:** when `reviewDecision === "pursue"` but no `applicationId` exists, copy states a Preparing application *should already* exist; appropriate as expectation, but verify automatic creation and clear an error when inconsistent. When outcome and application stage disagree, `outcomeType` takes precedence; this is display policy, not evidence of state repair. |
| `frontend/src/ApplicationArchivedReadOnly.test.tsx` | **TEST-13 Medium:** asserts archived task/interview/contact/document mutation controls are hidden and file download remains available, but does not attempt API writes (server authorization) or test switch from active to archived mid-edit. Useful UI regression only, not enforcement proof. |

**Proposed coverage:** **201/333 = 60.36%**, 132 pending. No operator data or production source changes.
