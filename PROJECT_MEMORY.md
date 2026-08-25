# JOLT Project Memory

This file records durable product contracts, project boundaries, and development rules.
Review it before changing existing JOLT behavior.

Last reviewed: 2026-08-25

## Product purpose

JOLT is a local job-search workflow system.

Its major workflows are separate:

1. Capture Jobs
   - acquires job evidence and capture batches.

2. Review Inbox
   - contains opportunities awaiting a human review decision.

3. Applications
   - contains durable job-application processes selected by the user.

4. LinkedIn Profile
   - manages professional-profile evidence and recommendations.

5. Market Insights
   - analyzes persisted market/capture evidence.

6. Settings & Data
   - configuration, preferences, exports, and data-management tools.

Do not merge these lifecycle boundaries merely because records share source evidence.

## Critical data invariants

### Applications are durable

A human Pursue decision creates durable application state.

Once an opportunity has an Application record, capture cleanup must never remove,
delete, or make that application disappear from the Applications workflow.

Application state outranks capture-batch lifecycle.

This includes:

- application status;
- timeline/events;
- tasks;
- interviews;
- contacts;
- documents;
- outcomes;
- preparation notes;
- review decision.

### Reviews are durable user state

A recorded human review decision is user-owned state.

Capture cleanup must not erase the decision merely because the source capture batch
is archived or removed from the pending inbox.

### Capture batches and selected cards are different things

The user may clear/archive a capture batch and its pending Review Inbox cards.

That operation must not destroy durable selected/reviewed/application cards that
originated from the same capture evidence.

Deleting or archiving capture provenance is not permission to delete user workflow state.

### Clear pending inbox

Expected behavior:

- pending Review Inbox cards may be cleared;
- relevant capture batches may be archived;
- reviewed opportunities must retain their review state;
- pursued opportunities/applications must remain in Applications;
- application history and evidence must remain intact.

Never implement this action as a broad deletion of Posting, ReviewDecision,
Application, ApplicationEvent, Outcome, task, interview, contact, or document state.

## Ownership hierarchy

When deciding whether data may disappear from a normal workflow, use this hierarchy:

1. Human-created durable application state
2. Human review decisions
3. Durable opportunity/posting identity
4. Source/evidence lineage
5. Capture-run lifecycle
6. Temporary UI state

A lower layer must not destroy a higher layer.

## Existing behavior rule

Before changing an existing feature:

1. Read this file.
2. Inspect the existing implementation.
3. Inspect regression tests covering neighboring workflows.
4. Check recent Git history when behavior is ambiguous.
5. Preserve previously approved behavior unless the requested change explicitly replaces it.

Do not redesign an established workflow solely to make a new feature easier to implement.

## Regression discipline

Every bug that crosses workflow boundaries should gain a regression test.

For capture cleanup specifically, tests must certify that:

- pending cards can disappear;
- the capture batch can be archived when appropriate;
- reviewed state survives;
- applications survive;
- application-index still returns pursued applications;
- application events/history survive.

## Job Search Preferences

Preferences are editable in Settings & Data.

Saving preferences and re-evaluating jobs are two separate HTTP operations.

The complete UI workflow is not transactional:

1. preferences POST can succeed;
2. evaluation refresh can subsequently fail.

Do not describe the two-request workflow as atomic.

Preference-based machine re-evaluation must not overwrite human review decisions
or application records.

## Classifier contract

Current certified source-first classifier baseline:

- engine: profile-rules-v10
- manual corpus: 182 jobs
- strict matches: 166/182
- strict accuracy: 91.2%
- v9 -> v10 regressions: 0
- hard-blocker invariant violations: 0

Do not create a new classifier version without new independent source evidence.

## Development workflow

Repository:
RafaelAlbaWebify/jolt

Local working copy:
C:\Users\ralba\Documents\GitHub\jolt

Rules:

- inspect exact GitHub state before changing code;
- make local changes explicitly;
- never use git add -A;
- never use git add .;
- stage only intended files;
- inspect the complete staged patch;
- do not mutate the production database during development/testing;
- tests must use temporary databases where practical;
- use a draft PR while a feature is incomplete;
- inspect the exact remote PR patch;
- merge only the expected PR head;
- squash merge;
- verify resulting main commit.

Required merge gates:

1. CI
2. Playwright acceptance
3. Full-cycle Playwright certification

All three must be green for the exact PR head.

## UI certification

Do not weaken acceptance/certification tests merely to make a feature pass.

The supported desktop viewport certification includes 1680x945.

If a view exceeds the certified layout, fix the UI structure rather than removing
the certification requirement unless the product requirement itself changes.

## Regression history

### 2026-08-25 - Review Inbox cleanup / Applications boundary

Observed:

Using "Clear pending inbox" caused previously selected application cards to disappear
from the Applications section.

Required behavior clarified:

The capture batch may be cleared/archived, but durable reviewed/application cards
must remain in JOLT.

Treat this as a workflow-boundary regression and add direct automated coverage before merge.

### 2026-08-25 - Job Preferences viewport

PR #329 introduced the Job Search Preferences editor.

Functional CI and Playwright acceptance passed, but Full-cycle Playwright certification
reported Settings & Data vertical overflow at 1680x945.

Fix the layout; do not weaken the viewport certification.

## Documentation maintenance

Update this file when:

- the user establishes a durable product behavior;
- an architectural boundary is clarified;
- a regression exposes an undocumented invariant;
- a workflow is intentionally replaced;
- merge/release rules change.

Do not fill this file with temporary debugging notes or transient implementation details.

- Mixed-batch cleanup regression coverage must verify that the application index still contains any pursued/applied opportunity after the capture batch is archived.
