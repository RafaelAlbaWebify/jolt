# Known Issues

Do not delete unresolved issues merely because they are old. Mark resolved with evidence and date.

## KI-001 — RESOLVED 2026-09-05 — Deterministic geography false US-state matches
- Module: AI review / hardline evidence
- Description: lowercase ordinary words such as `de`, `in`, `or`, or `me` could be interpreted as US state abbreviations and create false deterministic hardline evidence.
- Reproduction: real 2026-09-04 package produced `negative_evidence: ["de"]` on non-US vacancies.
- Resolution: PR #380 requires canonical uppercase state abbreviations while preserving full state names and explicit uppercase state constraints. Regression coverage retains `Frederick, MD`, `Austin, Texas`, `must reside in TX`, and lowercase-word negatives.
- Verification: PR #380 exact CI, Playwright acceptance and full-cycle gates passed before merge.
- Residual action: regenerate the real stored 79-job package on the current runtime so old bad evidence is not reused.

## KI-002 — RESOLVED/GUARDED 2026-09-05 — Local runtime can be stale relative to repository
- Module: Runtime/launcher/UI
- Description: an AI package was exported after repository fixes but still contained old review instructions because the running backend had loaded an older revision.
- Resolution: PR #384 compares process-loaded `loaded_git` identity with the current checkout and shows an always-visible restart-required guard when they differ. Developer diagnostics show loaded backend and repository checkout separately.
- Verification: PR #384 exact CI, Playwright acceptance and full-cycle gates passed before merge.
- Residual risk: the operator can still choose to ignore a visible warning; runtime acceptance must confirm the guard is clear before the next real package export.

## KI-003 — IMPLEMENTED/CI VERIFIED 2026-09-05 — LinkedIn Connections virtualized capture can be partial
- Module: LinkedIn Profile / Connections
- Description: earlier collector behavior could repeatedly observe the first visible contacts when LinkedIn used a nested virtualized scroll container; one prior run saw ~19 unique contacts while the profile showed 500+.
- Resolution: PR #377 scrolls the nearest nested Connections container before window fallback, records scroll strategy, distinguishes `complete` from `partial`, exports `network_capture_quality`, and warns AI that uncaptured people must never be treated as absent.
- Verification: PR #377 exact CI, Playwright acceptance and full-cycle gates passed before merge.
- Residual action: a future real LinkedIn Connections run should confirm live-site behavior; absence of that live run does not invalidate the bounded-sample semantics.

## KI-004 — RESOLVED 2026-09-05 — AI round-trip freshness/import acknowledgement UX incomplete
- Module: LinkedIn Profile / Settings & Data
- Description: durable visibility of imported AI updates and LinkedIn AI freshness was incomplete.
- Resolution: PR #382 rebuilt the useful PR #376 behavior on current main: persistent import receipt, imported sections/status, LinkedIn current/stale analysis panel and refresh after import. PR #376 was closed as superseded.
- Verification: PR #382 exact CI, Playwright acceptance and full-cycle gates passed before merge.

## KI-005 — P1 — Corrected real 79-job sequential review acceptance not yet imported
- Module: Review Inbox / AI exchange
- Description: the strict sequential protocol reviewed all 79 stored jobs and self-audit passed, but the returned update was intentionally not imported after KI-001 was discovered. The parser and importer are now corrected, so the package must be regenerated from the active runtime and the real round trip repeated.
- Status: OPEN.
- Workaround: none; do not import the pre-fix reviewed update.
- Blocking effect: blocks external-beta and real-prospect readiness.
- Next action: update/restart local JOLT, re-export stored capture `7a105d99-a81a-4486-a435-7db9a07eb0ab`, review sequentially, import, verify receipt and source-audit survivors.

## KI-006 — P3 — Version authority mismatch
- Module: Runtime/build metadata
- Description: FastAPI app/health/runtime reports `0.8.0`; `backend/pyproject.toml` reports package version `0.1.0`.
- Status: OPEN.
- Workaround: use Git commit plus loaded-runtime identity as authoritative build evidence.
- Blocking effect: production support/release ambiguity; no longer blocks stale-runtime detection because PR #384 exposes commit identity.
- Next action: establish one release-version source and derive runtime/API reporting from it.

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
- Verification: PR #385 head `528c921eeefe86ccaaaf38987cc5e9c6ad7f2d9d` passed CI run 1353, Playwright acceptance run 627 and full-cycle certification run 550 before merge as `09b78e194afe8cff219a6305b2a1df8cc3ea5101`.

## Historical resolved issues that must retain regression coverage
- Invalid LinkedIn authwall captures used as profile evidence — fixed by PR #374.
- Bulk AI review allowed high-fit ineligible jobs — protocol fixed by PR #378 and positive gate #375/#379.
- Capture cleanup could make Applications disappear — behavior invariant retained in `PROJECT_MEMORY.md`; keep mixed-batch/application-index regressions.
- Settings & Data viewport overflow at 1680x945 — fix product layout, never weaken certification.
