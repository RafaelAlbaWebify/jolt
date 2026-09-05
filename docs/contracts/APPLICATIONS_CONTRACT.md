# Applications Module Contract

## Responsibility
Own durable application lifecycle after a human pursue decision.

## Inputs
Pursued posting/review state, status transitions, tasks, interviews, contacts, documents, outcomes, preparation/readiness data.

## Outputs
Durable Application records, timeline/events, work items, preparation/readiness views, outcome evidence and application index entries.

## Guarantees
- an Application must survive capture archive/cleanup;
- lower-level capture/source lifecycle cannot make pursued applications disappear;
- transitions/outcomes are persisted and auditable;
- archive/restore/delete operations follow explicit lifecycle rules rather than broad cascade deletion.

## Dependencies
Posting identity, human review state, persistence layer, application work-item services.

## Failure behavior
Invalid transitions or unsafe deletes fail with explicit conflict/not-found behavior rather than silently mutating unrelated state.

## Non-responsibilities
Source capture, AI final career authority, market aggregation.