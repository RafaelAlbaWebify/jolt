# JOLT architecture audit — 2026-07-29

## Status

This document captures the architecture problem discovered while validating the Professional capture workflow and the Opportunities review queue.

The conclusion is deliberately conservative: do not keep patching deletion and UI behavior until the capture/import/review model is made explicit.

## User-intended product flow

The intended workflow is:

1. The user opens the Professional tab.
2. JOLT opens a visible Chromium browser.
3. The user signs in to LinkedIn if needed.
4. The user manually prepares the exact LinkedIn job-search results page.
5. JOLT captures the prepared page as evidence.
6. Extracted jobs appear in Opportunities as a pending review inbox.
7. The user reviews/classifies those jobs.
8. Once classified, they disappear from Opportunities.
9. Pursued jobs move to Applications / tracking.
10. Rejected, archived, stale, or deleted capture imports do not remain in the review inbox.

## Current observed mismatch

Live validation showed this state:

- Professional showed zero Professional capture runs after deleting Professional evidence batches.
- Opportunities still showed 151 pending jobs.
- The database audit showed `professional_capture_runs = 0`, but `capture_runs = 15` and `capture_items = 223`.
- The Opportunities queue was still fed by normal `capture_runs` / `capture_items`, not by the Professional evidence ledger.
- Attempted physical deletion of imported capture batches failed with SQLite foreign-key errors when deleting `postings`.

## Current capture systems

### Normal capture/import pipeline

Used by the existing Opportunities queue:

- `capture_runs`
- `capture_pages`
- `capture_items`
- `capture_artifacts`
- `source_documents`
- `postings`
- `evaluations`
- `review_decisions`
- `applications`
- `outcomes`
- application work-item tables

This pipeline owns job imports and feeds `/api/opportunity-index`.

### Professional Intelligence pipeline

Used by the experimental Professional evidence workflow:

- `professional_capture_runs`
- `professional_capture_artifacts`
- Professional evidence directory
- Professional browser profile
- Professional source registry and plan APIs

This pipeline currently does not cleanly own the jobs visible in Opportunities.

## Architectural mistakes found

### 1. Two capture universes

The UI suggests Professional owns capture, but Opportunities still reads from the normal capture/import pipeline. This creates a confusing state where Professional can be empty while Opportunities still contains old imported jobs.

### 2. Ownership is implicit instead of modeled

`Posting` is treated as a central record, but capture-batch deletion tries to infer whether a posting is safe to delete by checking reviews, applications, outcomes, source documents, and capture items.

That is fragile because more tables can reference `Posting` or its related records.

### 3. Physical deletion is unsafe as the default operation

The attempted cleanup failed with a foreign-key constraint on `postings`. That means the deletion function does not yet know the full dependency graph.

For user operations, JOLT should prefer archive/hide lifecycle states over physical deletion of central domain records.

### 4. Opportunities is not defined narrowly enough

The user-facing Opportunities tab should be a pending review inbox. It currently risks acting like a generic posting/evaluation index.

### 5. Tests were too synthetic

The passing tests created one capture, one item, one posting, and one evaluation. The live database contains many capture runs, duplicate imports, reviewed items, applications, and legacy data. Tests must include that shape.

## Target model

### CaptureBatch

One product-level concept should represent a capture/import batch, regardless of whether it originated from old supervised capture or new manual Professional capture.

Important states:

- `prepared`
- `capturing`
- `captured`
- `completed_with_gaps`
- `reviewed`
- `archived`
- `deleted`

### CaptureItem

Represents one extracted item from a batch. For job search pages, this maps to one potential job.

Fields should make ownership explicit:

- batch/capture run ID
- source URL
- source item ID
- imported posting ID
- item status
- evidence status

### Opportunity

The user-facing review concept. It can remain backed by `Posting` in the current code, but it needs explicit lifecycle state:

- `pending_review`
- `pursue`
- `reject`
- `defer`
- `archived`
- `tracked`

If no new table is created yet, the behavior can be represented using `review_decisions`, `applications`, and capture-run archive status.

### Application / Tracking

Only jobs the user has decided to pursue should become Applications. Applications should not disappear if a source capture batch is archived or hidden.

## Recommended immediate strategy

### Do not physically delete imported jobs yet

Physical deletion should wait until the schema audit proves the full dependency graph and tests cover real-world dependencies.

### Add archive/hide behavior

Use lifecycle states to hide stale capture imports from the review queue:

- Mark capture batches as archived or hidden.
- Filter Opportunities to show only items from active, non-archived capture batches.
- Preserve reviewed/applied/tracked jobs.

If the existing schema lacks a field to express archived capture batches, add one through a migration.

### Define Opportunities strictly

Default `/api/opportunity-index` should return only pending review inbox records:

- no application
- no review decision
- linked to an active capture item/run or explicitly created as manual pending intake
- not archived/hidden

Tracking views can call a broader API or pass a separate explicit flag.

## Proposed PR split

### PR 1 — Architecture audit and schema dependency tooling

- Add `tools/jolt-schema-fk-audit.py`.
- Add this architecture audit document.
- No product behavior changes.

### PR 2 — Safe archive model for capture imports

- Add a field or table to mark normal capture runs archived/hidden.
- Add migration.
- Add tests using multiple capture runs and duplicate postings.
- Do not delete central rows.

### PR 3 — Opportunities pending-review inbox semantics

- Filter `/api/opportunity-index` using active capture batches and pending-review state.
- Ensure classified items disappear from Opportunities.
- Ensure Applications/tracking still sees pursued jobs.

### PR 4 — Clean Professional manual capture workflow

- Extract only the good parts from experimental PR #187.
- Keep one top-level manual Chromium workflow.
- Do not mix cleanup/deletion architecture in this PR.

### PR 5 — Legacy cleanup UI/tooling

- After archive model is merged, offer safe preview/apply tooling to archive old imported batches.
- Avoid physical delete unless a separate maintenance mode is created and fully tested.

## Validation required before merge of behavior changes

The database audit should be run on the real local SQLite database and attached to validation evidence:

```powershell
uv --project backend run python tools/jolt-schema-fk-audit.py --output-dir "$env:USERPROFILE\Downloads\JOLT_SCHEMA_FK_AUDIT"
```

Behavior PRs must include tests for:

- multiple capture batches;
- duplicate postings shared across capture items;
- pending, reviewed, rejected, pursued, applied, and outcome records;
- legacy LinkedIn imports;
- manual audit fixture records;
- capture batch archive/hide behavior;
- application visibility after archive;
- Opportunities empty when there are no active pending review imports.
