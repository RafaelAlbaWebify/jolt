# Known Issues

Do not delete unresolved issues merely because they are old. Mark resolved with evidence and date.

## KI-001 — P1 — Deterministic geography false US-state matches
- Module: AI review / hardline evidence
- Description: `main` can treat lowercase ordinary words such as `de` as US state abbreviations, creating false `hardline_reject` evidence.
- Reproduction: real 2026-09-04 package produced `negative_evidence: ["de"]` on non-US vacancies.
- Status: FIX IN PR #380, NOT MERGED at control-layer creation.
- Workaround: do not import AI review output produced from known-bad deterministic evidence; regenerate after fix.
- Blocking effect: blocks clean end-to-end acceptance and real-prospect readiness.
- Next action: verify exact PR #380 gates, merge, update/restart runtime, regenerate package.

## KI-002 — P1 — Local runtime can be stale relative to repository
- Module: Runtime/launcher
- Description: an AI package was exported after repository fixes but still contained old review instructions because the running backend had not been updated/restarted.
- Reproduction: compare old package lacking `strict_sequential_per_job` against current `main` source.
- Status: OPEN.
- Workaround: `git pull`, confirm SHA, fully restart backend/frontend, verify exported package protocol markers.
- Blocking effect: can invalidate acceptance tests and user trust.
- Next action: add explicit runtime commit/version/staleness visibility.

## KI-003 — P2 — LinkedIn Connections virtualized capture can be partial
- Module: LinkedIn Profile / Connections
- Description: collector may repeatedly observe the first visible contacts when LinkedIn uses a nested virtualized scroll container; prior run saw ~19 unique contacts while profile showed 500+.
- Status: FIX PROPOSED IN PR #377; not merged/verified on main.
- Workaround: treat network capture as partial and never infer missing contacts are absent.
- Blocking effect: blocks trustworthy network analysis, not core job capture.
- Next action: verify PR #377 CI and real capture.

## KI-004 — P2 — AI round-trip freshness/import acknowledgement UX incomplete
- Module: LinkedIn Profile / Settings & Data
- Description: user cannot always see durable status that profile evidence is current/stale or that an AI update was accepted after navigation/reload.
- Status: FIX PROPOSED IN PR #376; prior frontend CI failure must be inspected/fixed before merge.
- Workaround: inspect exported/imported files and backend state manually.
- Blocking effect: trust/operability issue for non-developer use.
- Next action: inspect exact frontend failure, correct, rerun gates.

## KI-005 — P2 — Full 79-job sequential review acceptance not yet imported
- Module: Review Inbox / AI exchange
- Description: the new sequential protocol produced a 79-job reviewed update and self-audit passed, but import was deliberately stopped after discovering KI-001.
- Status: OPEN.
- Workaround: none; repeat from fresh corrected package.
- Blocking effect: the reasoning fix is implemented but the complete real-world round trip is not yet verified.
- Next action: complete R-009 then regenerate/review/import same stored capture.

## KI-006 — P3 — Version authority mismatch
- Module: Runtime/build metadata
- Description: FastAPI app/health reports `0.8.0`; `backend/pyproject.toml` reports package version `0.1.0`.
- Status: OPEN.
- Workaround: use Git commit as authoritative build identity.
- Blocking effect: complicates support/debugging and stale-runtime diagnosis.
- Next action: establish one version source or explicitly separate API schema/product/package versions.

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

## Historical resolved issues that must retain regression coverage
- Invalid LinkedIn authwall captures used as profile evidence — fixed by PR #374.
- Bulk AI review allowed high-fit ineligible jobs — protocol fixed by PR #378 and positive gate #375/#379.
- Capture cleanup could make Applications disappear — behavior invariant retained in `PROJECT_MEMORY.md`; keep mixed-batch/application-index regressions.
- Settings & Data viewport overflow at 1680x945 — fix product layout, never weaken certification.