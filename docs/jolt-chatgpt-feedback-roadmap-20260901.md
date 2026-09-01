# JOLT ↔ ChatGPT Feedback Roadmap

Date: 2026-09-01
Status: active implementation roadmap

## Architectural rule

JOLT is the local capture, storage, provenance, workflow and presentation layer.
ChatGPT is the reasoning layer.

The normal loop is:

1. JOLT exports current context plus relevant evidence.
2. ChatGPT performs judgment-heavy reasoning.
3. ChatGPT returns compact structured feedback and context updates.
4. JOLT validates, imports, stores and presents the results.
5. Human decisions and durable application state remain authoritative.

Local deterministic code should handle schema validation, IDs, provenance, hashing,
basic cleaning, persistence and UI calculations. It should not reimplement reasoning
that is better performed by ChatGPT.

## Universal feedback types

- classification
- extraction
- recommendation
- correction
- context_update
- market_signal
- gap_signal
- priority_update
- duplicate_link
- audit_result

## Phases

### Phase 1 — Universal exchange contract
Create one reusable input/output envelope for all JOLT ↔ ChatGPT workflows without
merging existing JOLT lifecycle boundaries.

### Phase 2 — Global context exchange
Export the current JOLT reasoning context from existing durable sources, including job
search preferences and other relevant profile/strategy state, and support controlled
context patches returned by ChatGPT.

### Phase 3 — Review Inbox round trip
Make the current capture → ChatGPT classification → JOLT import workflow the reference
implementation of the universal exchange pattern.

### Phase 4 — Market Insights round trip
Export bounded market evidence and import structured market signals, trends and summaries.

### Phase 5 — Skills-gap intelligence
Compare market evidence with proven professional/portfolio evidence and persist prioritized
gap signals and recommended evidence-building actions.

### Phase 6 — Job Search Preferences feedback
Use recent market, job-review and outcome evidence to propose search-strategy changes for
explicit human approval.

### Phase 7 — Applications intelligence
Export active application state for readiness, interview preparation, next actions and
follow-up recommendations; never overwrite durable human application state.

### Phase 8 — Outcomes and strategy learning
Analyze rejection, interview, offer, withdrawal and no-response outcomes and return
structured strategy adjustments.

### Phase 9 — LinkedIn Profile intelligence
Audit current LinkedIn profile evidence against market and target-role signals and return
proposed profile improvements.

### Phase 10 — Professional evidence / CV intelligence
Audit professional and portfolio evidence, identify supportable claims, role-specific
positioning and evidence gaps, and return structured recommendations.

### Phase 11 — Capture/search optimization
Analyze capture quality, search noise, duplicate rate, geography pollution and missing role
families and return proposed source/search improvements.

### Phase 12 — Universal data-quality audit
Audit stale, contradictory, duplicate or malformed evidence and return explicit repair
feedback while preserving provenance and durable user state.

## End state

Every major JOLT section participates in the same intelligence loop:

JOLT state/evidence → ChatGPT reasoning → structured JOLT feedback → human workflow.

JOLT should not need a separate local reasoning engine for each section.
