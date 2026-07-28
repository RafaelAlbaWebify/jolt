# JOLT product and recovery baseline

Status: canonical working baseline for product and engineering decisions

Baseline source commit: `1bb9ef3d19ca554a541dbba8807837a6ec6f7760`

## 1. Product definition

JOLT is a local-first job-search workbench for one primary user: Rafael Alba.

It exists to help Rafael find, capture, assess, prepare, track and learn from real job opportunities in one evidence-backed Windows application.

JOLT is not a generic CRM, autonomous application bot, scraping platform, multi-agent experiment or enterprise governance product.

### Product promise

JOLT should let Rafael complete this daily workflow reliably:

1. Discover or receive a real job opportunity.
2. Capture the original source and preserve evidence.
3. Create or update one canonical opportunity without duplicates.
4. Assess the opportunity against Rafael's real, versioned professional profile.
5. Review the assessment and decide whether to pursue it.
6. Prepare application material and interview guidance without inventing claims.
7. Track the application through controlled stages, tasks, contacts, interviews and follow-ups.
8. Preserve every material event and outcome.
9. Learn from accumulated opportunities, applications and outcomes.

### Non-goals

JOLT must not:

- submit applications automatically;
- message recruiters automatically;
- fabricate experience, qualifications or profile claims;
- perform uncontrolled scraping;
- turn a simple user workflow into an enterprise approval system;
- add architectural layers without a demonstrated product need;
- treat AI output as unquestionable truth.

## 2. Required product areas

### Opportunities

Purpose: maintain canonical records of real roles.

Minimum capabilities:

- manual opportunity entry;
- supervised source capture;
- source URL and evidence preservation;
- employer, title, location, work mode, compensation and requirements;
- duplicate detection and explicit duplicate handling;
- pursue, hold or reject decision;
- link to the resulting application.

### Fit assessment

Purpose: compare a real opportunity with Rafael's verified profile.

Minimum capabilities:

- explicit strengths;
- explicit gaps;
- risks and unknowns;
- evidence for each important conclusion;
- human-editable recommendation;
- profile version used for the assessment;
- no unsupported claims.

### Application preparation

Purpose: turn a pursued opportunity into a deliberate application.

Minimum capabilities:

- tailored CV guidance;
- application or recruiter-message draft support;
- interview preparation notes;
- role-specific evidence and gaps;
- user review before anything leaves JOLT.

### Application workflow

Purpose: show the real state of every application and the next required action.

Minimum capabilities:

- one canonical transition authority;
- controlled forward, correction and reopening transitions;
- current stage;
- next action and due date;
- contacts;
- interviews;
- documents and notes;
- immutable event history;
- immutable outcomes;
- explicit reopening reason.

### Professional intelligence

Purpose: collect bounded, user-supervised evidence from explicitly selected sources.

Minimum capabilities:

- one-click supervised capture;
- visible browser operation;
- bounded source and page behaviour;
- truthful progress;
- cooperative cancellation;
- clear distinction between user cancellation and engine failure;
- canonical evidence paths;
- review before extraction becomes trusted product data;
- safe retention and deletion.

### Market and outcome learning

Purpose: improve Rafael's job-search decisions from accumulated real data.

Minimum capabilities:

- role and skill patterns;
- application conversion by stage;
- recurring gaps;
- response and outcome patterns;
- transparent distinction between observed data and inference.

## 3. Intended user experience

JOLT should feel like a focused local desktop workbench.

The default landing experience should answer:

- What needs my attention today?
- Which opportunities should I review?
- Which applications need a follow-up?
- What changed since I last opened JOLT?

The interface should prioritise the user's next action over implementation concepts such as manifests, retention ledgers, readiness contracts or authorization states.

Advanced operational information may exist, but it must not obstruct the daily workflow.

## 4. Minimum daily-use vertical slice

The first recovery target is one complete, reliable path:

1. Start JOLT from Windows.
2. See the correct local database and runtime identity.
3. Add one opportunity manually or capture one selected source.
4. Review and save the canonical opportunity.
5. Record the decision to pursue it.
6. Create the application.
7. Set the current stage and next action.
8. Add and complete a follow-up task.
9. Record an interview or material event.
10. Record a final outcome.
11. Reopen when necessary without deleting historical facts.
12. Restart JOLT and verify that the complete history remains correct.

No secondary feature is allowed to delay this path.

## 5. Current implementation assessment

The repository contains substantial functionality, but product breadth and governance mechanisms have expanded faster than proven daily usability.

### Confirmed structural concerns from source inspection

- Professional capture executes synchronously inside the HTTP request rather than as a real background job.
- Backend progress fields exist but the frontend capture-run type and UI do not expose the complete progress model.
- User cancellation and engine failure are conflated in parts of the capture runtime.
- Evidence creation and run deletion use inconsistent directory shapes, creating a risk of orphaned evidence.
- Application stages are controlled by more than one layer rather than one canonical transition service.
- The interface can expose arbitrary active-stage changes beyond a strict transition graph.
- Reopening an application removes the structured outcome record after copying selected details to event text.
- Database migration is triggered from more than one startup path.
- Normal startup also performs dependency synchronization and schema mutation.
- Legacy capture and Professional Intelligence capture coexist as overlapping domains.
- Runtime identity is not sufficiently visible to prove which checkout, database, migration and evidence root are active.

These are source-level findings. A local bug is not considered fixed until reproduced and validated against the actual Windows checkout and real daily-use state.

## 6. Recovery order

Work must proceed in this order.

### Phase A: establish runtime truth

Before further code changes, collect and verify:

- local checkout path;
- current branch and commit;
- uncommitted changes;
- backend process ID, executable and command line;
- frontend process ID and command line;
- Python and Node versions;
- installed dependency identity;
- active SQLite database path;
- active evidence root;
- Alembic revision;
- frontend build identity;
- recent logs;
- current `.jolt` state and size breakdown.

### Phase B: certify the minimum vertical slice

Run the complete daily-use path against:

1. a disposable controlled database; and
2. a protected copy of the real daily-use database and `.jolt` state.

Record every failure as one of:

- confirmed defect;
- probable defect;
- design concern;
- environment or stale-state problem.

Only confirmed defects become immediate fixes.

### Phase C: fix blocking defects in narrow branches

Priority order:

1. canonical evidence path and deletion;
2. truthful asynchronous capture lifecycle;
3. live progress and cancellation semantics;
4. one application transition authority;
5. immutable outcome history;
6. runtime diagnostics and identity;
7. separation of install/update/migrate from ordinary startup;
8. removal or quarantine of the legacy capture domain;
9. UX simplification after correctness is established.

### Phase D: remove unnecessary complexity

After the vertical slice works, classify every module and screen as:

- essential;
- useful but secondary;
- duplicated;
- obsolete;
- speculative;
- removable.

Removal requires tests proving the daily workflow remains intact.

## 7. Engineering operating rules

### Local runtime is the product reality

GitHub is the code history. The Windows checkout, installed dependencies, database, `.jolt` state and running processes are the actual product.

### No fix without reproduction

The required sequence is:

1. observe the symptom;
2. capture evidence;
3. reproduce it;
4. identify the failing layer;
5. add or identify a regression test;
6. make the smallest change;
7. run focused tests;
8. run the real workflow;
9. verify the process is executing the changed code;
10. commit only after proof.

### Branch and commit discipline

- never work directly on `main`;
- one proven problem per branch;
- no unrelated refactoring in a bug fix;
- no merge without exact-head validation;
- preserve a rollback path;
- do not create many issues from speculative architecture observations.

### State protection

Before migrations, cleanup or destructive tests, protect:

- the SQLite database;
- `.jolt` configuration and evidence;
- user-created documents;
- capture manifests and artifacts.

Tests use disposable state or an explicit protected copy.

## 8. Code documentation standard

Comments are for future maintainers, including AI-assisted development, but they must explain intent rather than repeat syntax.

### Required documentation

Public domain services and non-obvious functions should document:

- responsibility;
- inputs and outputs when not obvious from types;
- side effects;
- transaction ownership;
- important invariants;
- deliberate failure modes;
- actions the function intentionally does not perform.

Example:

```python
def transition_application(application, target_status):
    """Move an application through the canonical transition graph.

    Persists an immutable transition event and rejects unsupported stage
    changes. The caller owns the database transaction.
    """
```

Inline comments should explain reasons and constraints:

```python
# Resolve evidence paths from the configured root, never from the process
# working directory, because Windows launchers may start JOLT elsewhere.
```

Do not add comments such as:

```python
# Increase the counter by one.
completed_count += 1
```

### Architecture decisions

Important cross-cutting decisions belong in short architecture decision records, not scattered comments. Initial ADR subjects:

- local-first storage and runtime identity;
- application transition authority;
- immutable outcome history;
- evidence directory contract;
- asynchronous capture execution;
- startup versus installation and migration;
- legacy capture retirement.

### Tests as executable documentation

Critical behaviour must have readable regression tests, including:

- deleting a capture removes the actual governed evidence directory;
- reopening preserves the structured previous outcome;
- invalid stage transitions are rejected;
- a cancellation is not reported as an engine failure;
- capture progress remains observable while work is running;
- restart preserves the complete application timeline;
- runtime diagnostics identify the active database and evidence root.

## 9. Definition of done for a bug fix

A fix is complete only when the record includes:

- reproduced symptom;
- root cause;
- affected local runtime identity;
- files changed;
- comments or documentation added where reasoning is non-obvious;
- regression test;
- focused test results;
- real workflow result;
- exact commit SHA;
- remaining risk;
- rollback method.

Passing isolated tests is not enough.

## 10. Product decision filter

Before implementing or retaining anything, ask:

> Does this help Rafael find, assess, prepare, track or learn from real job opportunities more reliably and clearly?

If the answer is no, the feature is postponed or removed.

If the answer is uncertain, it must not block the minimum daily-use vertical slice.
