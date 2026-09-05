# Market Intelligence / AI Exchange Contract

## Responsibility
Aggregate persisted job-market evidence and expose bounded, auditable context for ChatGPT-derived market/skills/search-strategy analysis.

## Inputs
Verified capture observations, current job-search preferences, stored AI feedback/context, application outcomes where relevant.

## Outputs
Market Intelligence views, bounded evidence corpus, market preparation/work-package sections, validated AI context updates.

## Guarantees
- market evidence comes from persisted captures rather than invented trend claims;
- bounded/rolling corpora must expose their limits/age;
- AI market summaries are derived and must not overwrite source observations;
- stale AI analysis must be distinguishable from current analysis when newer evidence exists;
- user-owned preferences and human application state are not patchable through market feedback.

## Dependencies
Capture/evidence persistence, global AI context, unified work-package exchange, application outcomes where included.

## Failure behavior
No market evidence yields not-analyzed/empty state rather than fabricated insight. Newer capture evidence can mark prior AI analysis stale.

## Non-responsibilities
Job-source capture, final job decision, profile-source capture, application transitions.