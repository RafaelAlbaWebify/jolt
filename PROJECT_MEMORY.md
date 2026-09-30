# JOLT Project Memory

This file records durable product contracts, project boundaries, and development rules.
Review it before changing existing JOLT behavior.

Last reviewed: 2026-09-30

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

## ChatGPT reasoning-layer contract

JOLT is the local capture, storage, provenance, workflow and presentation layer.
ChatGPT is the reasoning layer for judgment-heavy analysis.

The normal product feedback loop is:

1. JOLT freezes the relevant evidence scope (for normal discovery, only the new/deduplicated jobs in that batch).
2. JOLT exports one Unified AI Work Package containing that review scope plus bounded aggregate evidence/context sections.
3. ChatGPT performs source-first per-job hardline/fit review and the requested market/gap/strategy reasoning.
4. ChatGPT returns one schema-valid reviewed work-package update.
5. JOLT validates and imports the update atomically: per-job AI review and section feedback/recommendations may be persisted, while durable global AI context may change only through the package top-level `context_patch`.
6. Human review decisions and durable application state remain authoritative.

The Unified AI Work Package is the supported product workflow for durable AI strategy/context changes.
Individual section exchanges and standalone legacy review/preparation routes are compatibility/diagnostic
surfaces only and must not become alternate durable-context authorities.

Local deterministic code should handle schema validation, IDs, provenance, hashing,
basic cleaning, persistence and UI calculations. Do not build separate local Python
reasoning engines for tasks better performed by ChatGPT.

Reusable ChatGPT feedback categories are:

- classification;
- extraction;
- recommendation;
- correction;
- context_update;
- market_signal;
- gap_signal;
- priority_update;
- duplicate_link;
- audit_result.

Preserve existing workflow boundaries and durable ownership rules when implementing
this exchange architecture.

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

## Current review decision contract

Review Inbox presents only two explicit human actions:

- **Apply** — creates/retains durable Application state;
- **Reject** — records durable human rejection.

Taking no action means the opportunity remains pending. Historical `consider`, `defer`, and
`needs_more_information` records remain readable for compatibility but are not normal new UI decisions.

AI recommendation and human decision are separate concepts. Human state outranks AI recommendation.

## Intelligence freshness contract

`GET /api/ai-status` is the product freshness authority for AI/intelligence domains.
Browser localStorage receipts are not authoritative state and must not be used to decide whether intelligence is current.

Normal discovery review should refresh stale intelligence in the same Unified AI Work Package round trip.
A separate full strategy exchange is an advanced/diagnostic operation, not a required ritual after every batch.

## Applications / legacy Evaluation boundary

Durable Applications must remain visible and operable from Application + Posting/workflow state even if no
legacy Python `Evaluation` row exists. `Evaluation` may remain for legacy deterministic/capture support but
must not be a hidden prerequisite for Applications or a second user-facing reasoning authority.

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

Required production-affecting merge gates:

1. backend CI (pytest/Ruff/Pyright)
2. frontend tests/build
3. Playwright acceptance / sidebar-kanban
4. Full-cycle Playwright + viewport certification
5. Windows clean-install certification
6. Migration recovery certification
7. Reproducible release certification
8. Windows script contract

All applicable gates must be green for the exact PR head. A transient/flaky failure must either be
reproduced and fixed or pass an unchanged isolated rerun before merge; do not weaken the test.

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


## 2026-09-30 architecture consolidation

The architecture audit identified disconnected/duplicated AI update paths. The remediation is now durable product policy:

- PR #464: discovery batch review + aggregate intelligence refresh share one Unified AI Work Package;
- PR #465: backend-owned AI freshness status replaces browser-local import receipt authority;
- PR #466: Applications are independent from legacy Evaluation;
- PR #467: only the Unified AI Work Package may mutate durable global AI context; legacy/section routes are deprecated.

Do not reintroduce section-level durable `context_patch` writes or new product flows on deprecated AI routes.


## 2026-09-30 planned UX simplification complete

The post-architecture simplification sequence is complete:

- PR #468 synchronized repository project control with the unified intelligence architecture;
- PR #469 simplified Settings & Data around backend-owned intelligence status, with deliberate strategy refresh and legacy compatibility tooling kept in Advanced;
- PR #470 made Applications operationally denser with an Active / Interviewing / Offers / Overdue scorecard and Board/List views while preserving lifecycle semantics.

The product-development posture is now **production use first**. Do not invent another UI or architecture program merely because no milestone is active. Record concrete operator friction during real job-search work and change JOLT only when that evidence, a demonstrated source-coverage need, or an explicit compatibility decision justifies it.


## 2026-09-30 official-source work-model authority

A production classification review found a real source conflict: LinkedIn can label a vacancy Remote while the employer's official ATS classifies the same vacancy Hybrid.

Durable rule:
- LinkedIn is discovery evidence, not final authority for work model or hiring location when an employer-controlled source exists.
- Official ATS/careers/company job pages outrank LinkedIn for location and work model.
- A LinkedIn Remote label alone must never become confirmed remote eligibility.
- Review contract 1.2 records linkedin_work_model, official_work_model, authoritative_source, official_source_url, source_conflict, remote_status, location_verification_status and source_confidence.
- When LinkedIn and the official source diverge, keep technical fit available but cap geography at conditional/unknown and the AI decision at conditional until the conflict is resolved.
- Do not convert a conflict directly into SKIP_BY_LOCATION unless authoritative evidence proves the candidate is ineligible; unresolved flexibility remains a verification task.
