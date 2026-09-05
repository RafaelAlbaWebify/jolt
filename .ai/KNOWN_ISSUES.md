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

## KI-010 — P1 — LIVE ACCEPTANCE OPEN — LinkedIn profile detail false-complete on lazy-loaded sections
- Module: LinkedIn Profile / candidate evidence
- Description: a real fresh Licenses & certifications capture could be marked `stable_at_document_end` / complete while retaining only roughly the first ten credentials. The PR #389 collector jumped directly to the absolute footer, which can skip LinkedIn lazy-load triggers that fire only when intermediate content enters the viewport.
- Runtime reproduction: capture `4d99d167-b6d9-4e88-aa05-9c7d84d860d3` on 2026-09-05 ended around IBM Project Manager and omitted known later credentials such as IBM Cybersecurity Analyst, AWS Cloud Solutions Architect, AWS Cloud Technology Consultant and Google Cybersecurity.
- Bug class: evidence bug / completeness-contract bug. The synthetic bottom-triggered lazy-load regression was too weak to model the live site.
- Implemented resolution: PR #390 starts profile-detail capture at the top, advances progressively through intermediate viewport thresholds, requires repeated stability at the true document end, records furthest scroll position/final document height, exposes recorder-owned `capture_metadata`, and fail-closes legacy LinkedIn `/details/` captures that predate progressive traversal.
- Verification: PR #390 exact head `6db3e53cb0929e2ce70aa6ce865f0dbac424d7f0` passed CI run 1367, Playwright acceptance 636 and full-cycle certification 559; squash-merged as `e12f1befe0c1ff0d56d151b66215863a9595e60a`.
- Status: code/test fix is complete, but live acceptance remains OPEN.
- Blocking effect: blocks external-beta promotion and the second real AI cycle because candidate evidence must not be trusted until a fresh live profile-detail recapture demonstrates later credentials and `progressive_traversal_verified=true`.
- Next action: update/restart local JOLT at current main, recapture Licenses & certifications, inspect the full list and exported capture metadata, then continue the second real capture/review/import cycle.

## Historical resolved issues that must retain regression coverage
- Invalid LinkedIn authwall captures used as profile evidence — fixed by PR #374.
- Bulk AI review allowed high-fit ineligible jobs — protocol fixed by PR #378 and positive gate #375/#379.
- Capture cleanup could make Applications disappear — behavior invariant retained in `PROJECT_MEMORY.md`; keep mixed-batch/application-index regressions.
- Settings & Data viewport overflow at 1680x945 — fix product layout, never weaken certification.
- Structured AI import errors rendered `[object Object]` — fixed by PR #387; keep structured validation-path regression.
