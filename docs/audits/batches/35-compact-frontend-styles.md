# Batch 35 — Four small frontend styling surfaces

Baseline `main` `f34749746a48c509b1f3c0cc07a8d3b49a1c606a`. Entire source reads of four CSS files. `ProductionUXRefresh.css` was sampled but **not counted**, because its ~55 KB complete cascade was not reviewed here. No visual test execution.

- `frontend/src/OpportunityApplicationHandoff.css`: responsive flex-to-column handoff at 760px, readable stage chip; hard-coded light colors imply dark/theme consistency risk, **STYLE-05 low**.
- `frontend/src/RuntimeIdentity.css`: global diagnostic panel uses partially translucent dark backgrounds and `var(--muted-text)` without fallback; verify inherited theme contrast and token existence, **STYLE-06 low**. Long paths are appropriately wrap-safe.
- `frontend/src/ReleaseBlockingUx.css`: **STYLE-07 medium accessibility:** `.opportunity-row .score span { font-size:0 }` hides underlying text visually and uses `::after` CSS-generated status words. Screen-reader behavior of generated content is inconsistent; UI state must be present in semantic HTML and tested with assistive technology. Rule duplication and overrides also increase cascade complexity. Confirm what screen readers actually announce.
- `frontend/src/EvidenceWorkspace.css`: fixed light palette, but responsive 900/720px grid reflows and horizontal text wrapping are positive. Evidence inspector occupies full viewport with `position: fixed`, requiring separate focus-trap/escape/body-scroll tests in component code; stylesheet does not establish those behaviors (**STYLE-08 unverified interaction dependency**).

**Counting:** 4 unique non-test rows move from PENDING to audited. Non-test register coverage **191/300 = 63.67%**, pending 109; all-row legacy **203/333 = 60.96%**, pending 130. Counts are based on the existing register, not fresh production tree certification. Static findings not necessarily live defects.
