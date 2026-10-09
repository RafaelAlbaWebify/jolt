# Known Issues

Do not delete unresolved issues merely because they are old. Mark resolved with evidence and date.

## KI-001 — RESOLVED 2026-09-05 — Deterministic geography false US-state matches
- Module: AI review / hardline evidence
- Description: lowercase ordinary words such as `de`, `in`, `or`, or `me` could be interpreted as US state abbreviations and create false deterministic hardline evidence.
- Reproduction: real 2026-09-04 package produced `negative_evidence: ["de"]` on non-US vacancies.
- Resolution: PR #380 requires canonical uppercase state abbreviations while preserving full state names and explicit uppercase state constraints. Regression coverage retains `Frederick, MD`, `Austin, Texas`, `must reside in TX`, and lowercase-word negatives.
- Verification: PR #380 exact CI, Playwright acceptance and full-cycle gates passed before merge; corrected real 79-job package generated without the false lowercase-state evidence.

## KI-002 — RESOLVED/GUARDED 2026-09-05 — Local runtime can be stale relative to repository
- Module: Runtime/launcher/UI
- Description: an AI package was exported after repository fixes but still contained old review instructions because the running backend had loaded an older revision.
- Resolution: PR #384 compares process-loaded `loaded_git` identity with the current checkout and shows an always-visible restart-required guard when they differ. Developer diagnostics show loaded backend and repository checkout separately.
- Verification: PR #384 exact CI, Playwright acceptance and full-cycle gates passed before merge; later real restart acceptance showed the guard clear with imported state preserved.

## KI-003 — IMPLEMENTED/CI VERIFIED 2026-09-05 — LinkedIn Connections virtualized capture can be partial
- Module: LinkedIn Profile / Connections
- Description: earlier collector behavior could repeatedly observe the first visible contacts when LinkedIn used a nested virtualized scroll container; one prior run saw ~19 unique contacts while the profile showed 500+.
- Resolution: PR #377 scrolls the nearest nested Connections container before window fallback, records scroll strategy, distinguishes `complete` from `partial`, exports `network_capture_quality`, and warns AI that uncaptured people must never be treated as absent.
- Verification: PR #377 exact CI, Playwright acceptance and full-cycle gates passed before merge.
- Residual action: a future real LinkedIn Connections run should confirm live-site behavior; absence of that live run does not invalidate the bounded-sample semantics.

## KI-004 — RESOLVED 2026-09-05 — AI round-trip freshness/import acknowledgement UX incomplete
- Module: LinkedIn Profile / Settings & Data
- Description: durable visibility of imported AI updates and LinkedIn AI freshness was incomplete.
- Resolution: PR #382 rebuilt persistent import receipt, imported sections/status, LinkedIn current/stale analysis panel and refresh after import. PR #376 was closed as superseded.
- Verification: PR #382 exact green gates plus real 2026-09-05 import/restart acceptance; the receipt persisted after restart.

## KI-005 — RESOLVED 2026-09-05 — Corrected real 79-job sequential review acceptance
- Module: Review Inbox / AI exchange
- Description: the first strict sequential 79-job return could not be trusted until the deterministic geography parser and importer gates were corrected and a fresh package was reviewed/imported on the active runtime.
- Resolution: package `2ebeeeca-42bb-473f-a220-7d3b1bc0e860` was reviewed under contract 1.1 in strict sequential mode and successfully imported on 2026-09-05 after a schema-corrected V2 return.
- Runtime result: 79 jobs reviewed exactly once; 76 reject / 1 strong_pursue / 1 pursue / 1 conditional. Settings & Data showed Imported, seven intelligence sections updated and Review Inbox updated.
- Persistence verification: a full local JOLT restart preserved the import receipt, Market Insights and Review Inbox decisions.
- Residual action: the second consecutive real cycle is still required for real-prospect readiness.

## KI-006 — RESOLVED 2026-09-05 — Version authority mismatch
- Module: Runtime/build metadata
- Description: FastAPI app/health/runtime reported `0.8.0` while `backend/pyproject.toml` reported `0.1.0`.
- Resolution: PR #388 aligned backend package metadata to `0.8.0` and added regression coverage requiring pyproject, FastAPI app version and `/api/health` version to remain equal.
- Verification: PR #388 exact-head gates passed before merge.
- Residual risk: a future release-process redesign may introduce a single generated source rather than parity enforcement, but the former runtime/package mismatch is closed.

## KI-007 — P3 — Historical documentation can describe superseded architecture
- Module: Documentation
- Description: architecture/capture docs record important historical failures and proposed fixes but are not all current-state documents.
- Status: MANAGED by `.ai/` control layer.
- Workaround: use source/test evidence first and `.ai/` as bootstrap; treat dated docs as historical unless referenced.
- Blocking effect: context reconstruction risk.
- Next action: maintain `.ai/` and mark superseded docs when touched.

## KI-008 — P3 — Large route composition surface
- Module: Backend architecture
- Description: `backend/src/jolt/main.py` composes many responsibilities and endpoints, increasing coupling/read cost.
- Status: TECHNICAL DEBT, not an immediate blocker.
- Workaround: bounded module-specific service files already contain most logic.
- Next action: only split routing when doing related work; avoid gratuitous rewrite.

## KI-009 — RESOLVED 2026-09-05 — AI review contract allowed omitted capture postings
- Module: Review Inbox / AI import contract
- Description: contract 1.1 instructed ChatGPT to return every captured posting exactly once, but the importer enforced duplicates and outsiders without enforcing exact returned-set completeness. An omitted posting could therefore pass validation.
- Resolution: PR #385 requires the returned posting-id set to equal the capture posting-id set for contract 1.1 and rejects omissions before any AI review rows are written. Legacy contract 1.0 behavior is preserved.
- Verification: PR #385 head `528c921eeefe86ccaaaf38987cc5e9c6ad7f2d9d` passed CI run 1353, Playwright acceptance run 627 and full-cycle certification run 550 before merge.

## KI-010 — RESOLVED 2026-09-19 — LinkedIn profile detail false-complete on lazy-loaded sections
- Module: LinkedIn Profile / candidate evidence
- Description: a real fresh Licenses & certifications capture could be marked `stable_at_document_end` / complete while retaining only roughly the first ten credentials. The PR #389 collector jumped directly to the absolute footer, which can skip LinkedIn lazy-load triggers that fire only when intermediate content enters the viewport.
- Runtime reproduction: capture `4d99d167-b6d9-4e88-aa05-9c7d84d860d3` on 2026-09-05 ended around IBM Project Manager and omitted known later credentials such as IBM Cybersecurity Analyst, AWS Cloud Solutions Architect, AWS Cloud Technology Consultant and Google Cybersecurity.
- Bug class: evidence bug / completeness-contract bug. The synthetic bottom-triggered lazy-load regression was too weak to model the live site.
- Implemented resolution: PR #390 starts profile-detail capture at the top, advances progressively through intermediate viewport thresholds, requires repeated stability at the true document end, records furthest scroll position/final document height, exposes recorder-owned `capture_metadata`, and fail-closes legacy LinkedIn `/details/` captures that predate progressive traversal.
- Verification: PR #390 exact head `6db3e53cb0929e2ce70aa6ce865f0dbac424d7f0` passed CI run 1367, Playwright acceptance 636 and full-cycle certification 559; squash-merged as `e12f1befe0c1ff0d56d151b66215863a9595e60a`.
- Resolution evidence: fresh live 2026-09-19 LinkedIn profile-detail capture reached later Licenses & certifications that the earlier collector missed; the external-beta/profile acceptance gate passed and subsequent real job-review cycles proceeded.
- Blocking effect: none. Keep progressive-traversal and fail-closed legacy-detail regression coverage.

## Historical resolved issues that must retain regression coverage
- Invalid LinkedIn authwall captures used as profile evidence — fixed by PR #374.
- Bulk AI review allowed high-fit ineligible jobs — protocol fixed by PR #378 and positive gate #375/#379.
- Capture cleanup could make Applications disappear — behavior invariant retained in `PROJECT_MEMORY.md`; keep mixed-batch/application-index regressions.
- Settings & Data viewport overflow at 1680x945 — fix product layout, never weaken certification.
- Structured AI import errors rendered `[object Object]` — fixed by PR #387; keep structured validation-path regression.


## KI-011 — RESOLVED 2026-09-28 — Interrupted discovery batches could remain in non-terminal state after backend restart
- Module: Capture Jobs / saved-search discovery.
- Resolution: PR #437 reconciles interrupted scheduled/running work on startup while preserving queued work.
- Blocking effect: none.

## KI-012 — RESOLVED 2026-09-30 — Daily UX exposed development-era terminology, duplicate actions and excessive vertical growth
- Module: Review Inbox / Applications / Settings / Market Insights.
- Resolution: UX stabilization PRs #442/#447/#448/#449/#450/#452, live audit #454, production density #455–#459, Review Inbox redesign #460–#462 and Market Insights dashboard #463.
- Verification: exact-head automated gates plus real operator screenshots/live audit at the certified viewport.
- Blocking effect: none; future UX changes should be friction-driven rather than broad speculative redesign.

## KI-013 — RESOLVED 2026-09-30 — AI workflows had multiple durable-context authorities and disconnected freshness loops
- Module: AI exchange / Market Insights / Applications / Settings & Data.
- Description: daily discovery review, market/strategy refresh, browser-local import receipts, legacy Evaluation dependencies and section-level context patches could diverge.
- Resolution:
  - PR #464: one batch-scoped Unified AI Work Package carries frozen new-job review plus aggregate intelligence context;
  - PR #465: backend `/api/ai-status` owns freshness;
  - PR #466: Applications no longer require legacy Evaluation;
  - PR #467: Unified AI Work Package is the sole durable context authority; section/legacy routes are deprecated compatibility surfaces.
- Verification: PR #467 exact head passed backend, frontend rerun, Playwright/sidebar-kanban, full-cycle, clean-install, migration recovery, reproducible release and Windows scripts.
- Blocking effect: none.
- Residual rule: do not add new product workflows to deprecated individual exchange/import routes.

## Current open issue state
- No open GitHub product issues as of 2026-09-30 after issue #441 was closed completed.
- No known unresolved P0/P1 blocker.


## 2026-10-03 Indeed acceptance status

- No unresolved P0/P1 product defect is known.
- The supervised Indeed adapter is **not yet production-accepted** despite green exact-head CI.
- The 2026-10-02 real three-page run successfully navigated pages 1–3 and deduplicated by `jk`, but exposed secondary action anchors being treated as titles. PR #491 corrected this with title-specific selectors and regression coverage.
- The same run's HTTP 422 was produced by an older loaded backend, not the current schema; the runtime mismatch guard had already reported that stale process.
- Required closure evidence: restart current JOLT, run a fresh post-#491 three-page capture, confirm clean title/company/location/detail identity and successful API ingestion.


## KI-014 — OPEN 2026-10-09 — Canonical AI project context is stale
- Module: project governance / AI development workflow.
- Evidence: `.ai/CONTEXT.md` and `PROJECT_MEMORY.md` last reviewed 2026-10-03; `.ai/TEST_STATUS.json` last updated 2026-09-30. PRs #510–#522 (Indeed optimization, source-integrity audit and InfoJobs foundation) were merged without matching canonical context updates.
- Impact: developers may repeat work, assert inaccurate readiness or overlook access blockers despite a pre-existing `.ai/SESSION_PROTOCOL.md`.
- Mitigation: see `docs/JOLT_CURRENT_HANDOVER_2026-10-09.md` for measured handover. Synchronize canonical state before starting further feature work; apply mandatory session protocol on every turn involving repo changes.
- Blocking effect: blocks new source-adapter feature development until project state is reconciled; does not block normal existing JOLT use.

## KI-015 — OPEN 2026-10-09 — InfoJobs live integration lacks developer API access
- Module: InfoJobs source adapter.
- Evidence: user explicitly confirmed no developer Client ID or Client Secret on 2026-10-09. PRs #521/#522 added parser and read-only authenticated preview with mock tests, but no real API calls or production ingestion.
- Impact: InfoJobs is **not operational**; passing 8/8 CI does not prove API compatibility or access.
- Next action: verify practical official access requirements, then document go/no-go. If unavailable, evaluate a compliant supervised browser alternative or change portal priority.
- Blocking effect: prevents real API acceptance, not LinkedIn/Indeed use.

## KI-016 — PARTIALLY RESOLVED 2026-10-09 — Indeed source extraction latency and acceptance
- Module: Indeed supervised capture.
- Evidence: 2026-10-09 multipage run: 40/40 verified, ~3.99 s/job mean; PR #519 eliminated measured ~26s missing-selector waits; PR #520 read-only audit passed all 40/40 against persisted capture JSON and immutable source text.
- Residual uncertainty: live-site-to-captured-description word-for-word fidelity and normalized Posting.description equality not audited. Preserve this distinction.
- Blocking effect: none for normal Indeed use; revisit if specific evidence gap or regression arises.


## KI-015 update — 2026-10-09 — Developer registration unavailable in user session
- Direct operator evidence: logged-in InfoJobs Developers > Manage Apps screen displays: "The registration of new apps is currently unavailable. We hope to offer it again in shortly. Sorry for the inconvenience."
- Impact: cannot register a new developer application to obtain Client ID / Secret using the current official UI; the API preview in PR #522 remains unavailable for live acceptance.
- Decision: keep official API foundation but suspend credential-dependent integration work. Evaluate permitted supervised browser capture and site terms, or prioritize a source with a feasible authorized access method. Do not ask user to create impossible credentials or use another person's API keys.
- Evidence scope: the registration UI was unavailable when checked, not proof that registration is permanently closed.
