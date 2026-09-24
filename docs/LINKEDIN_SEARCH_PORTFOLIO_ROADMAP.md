# LinkedIn Search Portfolio and Discovery Batch Roadmap

Date: 2026-09-23
Status: COMPLETE
Accepted release: `1157942fec504b3d41c6371046ae04afc8111709`

## Goal

Replace the current repeated one-search-at-a-time operator loop with one user action that runs a saved portfolio of LinkedIn job searches sequentially, preserves per-search provenance, consolidates duplicate postings, and produces one review set.

The certified per-search capture engine remains the lower-level primitive.

## Architectural invariants

- One LinkedIn search definition remains one provenance unit.
- One search execution remains one `CaptureRun`; a discovery batch groups multiple runs.
- Existing multipage capture, card identity verification, retry behavior, fail-closed LinkedIn access detection, canonical posting ingestion, and per-run evidence are not rewritten for the batch feature.
- LinkedIn page state such as `currentJobId`, `origin`, `refresh`, and `start` is not part of canonical search identity.
- Per-search capture remains bounded to the currently certified contract (100 jobs / 10 pages) until separate evidence justifies changing it.
- A discovery batch may contain many bounded search runs and may therefore exceed 100 raw appearances overall.
- Human interaction target: select saved searches -> start once -> wait for batch -> one consolidated AI review round trip.
- Existing production readiness remains the certified baseline until this new feature passes its own exact-head gates and real acceptance.

## Phase 1 — Search identity and saved portfolio

Deliver:
- canonical LinkedIn search URL normalization including pagination-state removal;
- durable saved-search model;
- CRUD-style local API for labels, URLs, notes, enabled state, and per-search limits;
- durable discovery-batch and batch-search records ready for orchestration;
- automated migration and regression tests.

Acceptance:
- page 1 / page 2 / page 3 URLs from the same LinkedIn search normalize to the same canonical URL;
- different keyword searches remain distinct;
- saved searches survive restart through SQLite persistence;
- existing single-search capture contract remains unchanged.

## Phase 2 — Sequential discovery orchestration

Deliver:
- start one batch from selected saved searches;
- execute searches sequentially;
- reuse the certified per-search capture behavior;
- keep each search as its own `CaptureRun`;
- persist progress/status/error per search;
- batch-level status and aggregate metrics;
- stop safely on authentication/checkpoint/safety failures;
- bounded handling of ordinary search-specific failures.

Preferred runtime shape:
- open one persistent Chromium context for the batch;
- navigate to each canonical saved search;
- run the existing page/card/detail capture logic for that search;
- submit each search independently to JOLT ingestion;
- move to the next search without operator action.

Acceptance:
- at least two distinct saved searches complete from one user action;
- each produces an independent capture run and page evidence;
- batch status survives frontend refresh;
- failure in one bounded search cannot corrupt another completed run.

## Phase 3 — Consolidated review set

Deliver:
- build a review set from all successful capture runs in one discovery batch;
- canonical-posting deduplication across searches;
- distinguish raw appearances, unique postings, previously known postings, and current-review postings;
- remove the current `latest capture only` assumption from the batch review path;
- validate one return set exactly against the batch review set.

Acceptance:
- a vacancy appearing in several searches is reviewed once;
- provenance still records every search in which it appeared;
- one export/import round trip covers the complete batch review set;
- no returned posting can fall outside the batch set and no batch posting can be omitted.

## Phase 4 — Capture Jobs UI

Deliver UI based on the approved mockup:
- Saved Search Portfolio table;
- checkboxes for batch selection;
- editable human-friendly labels;
- three-dot row menu for edit and delete; enabled/disabled state is editable in the saved-search form;
- add-search form;
- canonical LinkedIn URL field;
- per-search max jobs/pages;
- discovery batch progress view;
- captured/new/duplicate counts;
- one prominent `Start Discovery` action;
- completed-batch action to download one consolidated AI review exchange and import the returned JSON;
- legacy single-search launcher retained as an explicit fallback, not the primary workflow.

Acceptance:
- ordinary weekly workflow requires no copying/pasting after searches are configured;
- user can see which search is running and which completed/failed;
- existing single-search diagnostics remain available internally.

## Phase 5 — Real acceptance and production recertification

Run:
- backend lint/format/type/tests;
- frontend tests/build;
- Playwright acceptance;
- full-cycle certification;
- migration recovery;
- production clean install;
- reproducible release;
- real authenticated LinkedIn multi-search batch on the supported Windows workstation;
- one consolidated AI review/import acceptance.

Final proof must include:
- exact release commit;
- selected saved-search definitions;
- capture runs produced;
- total raw appearances;
- unique canonical postings;
- duplicates consolidated;
- new/review-set count;
- successful review import and restart persistence.

## Explicit non-goals for this workstream

- raising a single-search capture above 100 jobs without separate evidence;
- parallel LinkedIn searches;
- unattended login/CAPTCHA/checkpoint bypass;
- auto-apply or messaging;
- replacing the existing capture engine with a new crawler;
- generating arbitrary LinkedIn filter URLs before saved real LinkedIn URLs are proven sufficient.


## Completion evidence — 2026-09-24

R-025 passed real authenticated acceptance on the supported Windows workstation.

- Release commit under test: `1157942fec504b3d41c6371046ae04afc8111709`
- Exact main-push certification: CI, Playwright acceptance, Full-cycle Playwright certification, Production clean-install certification, Migration recovery certification, and Reproducible release certification all passed.
- Discovery Batch: `02c529d0-bae8-4cc1-8288-a7575146b515`
- Saved searches executed sequentially: 2/2 completed
- Capture runs: `8f88f7ed-b55a-4768-aa59-deec5b29085c` and `2c903795-e02f-4227-b0a1-0804543fce30`
- Raw captured items: 50
- Verified items: 50
- New postings in batch metrics: 47
- Duplicate count in batch metrics: 3
- Unique canonical postings in review exchange: 50
- Already-reviewed postings excluded from first materialization: 3
- Frozen current review set: 47
- One consolidated 47-job ChatGPT review returned and imported successfully
- Full JOLT restart after import: PASS; discovery batch/review state persisted
- Local operator evidence:
  - `JOLT_LINKEDIN_PORTFOLIO_ACCEPTANCE_20260924_110205.json`
  - `JOLT_LINKEDIN_PORTFOLIO_REVIEW_ACCEPTANCE_20260924_114024.json`

Outcome: the ordinary discovery workflow is now saved-search selection -> one Start Discovery action -> sequential supervised capture -> one deduplicated AI review round trip -> durable imported state.
