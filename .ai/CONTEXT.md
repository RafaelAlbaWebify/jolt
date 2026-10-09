# JOLT AI Bootstrap Context

## Verified source integration update — 2026-10-09
- Canonical context drift from PRs #510–#522 is being reconciled in PR #523; follow `.ai/SESSION_PROTOCOL.md` and the evidence boundary in `docs/JOLT_CURRENT_HANDOVER_2026-10-09.md`.
- Indeed: 40/40 verified across four observed pages on 2026-10-09 at ~3.99 s/offer; 26 newly ingested, 14 duplicates; local read-only capture artifact/source-document audit 40/40 passed with zero failures. Site-to-captured-description fidelity and normalized Posting.description equality **not** asserted.
- InfoJobs: PRs #521/#522 implemented a mock-tested adapter and authenticated read-only preview, but no live API access or ingestion; the user has **no developer Client ID or Client Secret**. Mark live integration BLOCKED rather than complete.
- Tecnoempleo and Welcome to the Jungle: no implemented adapters, access feasibility unverified.
- Keep the earlier 100% operability statement strictly limited to the previously certified Windows local-first JOLT product; it is **not** a claim that three new portal integrations are operational.
- Current active next step: finish documentation reconciliation, check CI/merge, then assess lawful InfoJobs access before further code implementation.

JOLT is a local-first, single-user Windows job-search evidence, review, application-tracking, LinkedIn-profile and market-intelligence workbench. It preserves source evidence, deduplicates opportunities, exposes structured review data, persists durable human/application state and exchanges judgment-heavy analysis with ChatGPT through validated JSON contracts.

## Current production state — 2026-10-03
- Production operability: **100%** within the certified local-first single-user Windows x64 boundary.
- Current main baseline: `9f484a6dcc98e4225cb3e8afe9dccc89dca2cce5`.
- No known unresolved P0/P1 blocker.
- No open GitHub product issues; UX issue #441 closed completed on 2026-09-30.
- Normal discovery uses the production saved-search portfolio and frozen discovery batches.
- Review Inbox is a split-view decision workspace. Human choices are **Apply**, **Reject**, or leave pending.
- Applications are durable and no longer depend on legacy Python `Evaluation` rows.
- Market Insights is an action-oriented dashboard with current application/interview metrics plus persisted AI market intelligence.

## Normal intelligence workflow
The supported product path is:

`Capture Jobs -> frozen discovery batch -> Unified AI Work Package -> ChatGPT review + aggregate intelligence refresh -> one validated import -> Review Inbox / Market / Search / Application / Profile intelligence`.

Rules:
- The batch review surface contains only the new/deduplicated jobs frozen for that batch.
- Aggregate intelligence may use the bounded evidence/context exchanges carried in the same package.
- Durable global AI context may be updated **only** through the Unified AI Work Package top-level `context_patch`.
- Individual section exchanges and standalone legacy review/preparation routes remain deprecated compatibility/diagnostic surfaces; do not build new product workflows on them.
- Backend `GET /api/ai-status` is the intelligence-freshness authority. Browser `localStorage` is not product state.

## Product lifecycle
`capture/manual intake -> preserved evidence -> normalized posting -> AI review evidence -> Review Inbox -> human Apply/Reject/pending -> durable Application -> events/outcome -> aggregate intelligence feedback`.

Major user modules:
- Capture Jobs — what new opportunities are available?
- Review Inbox — is this worth applying to?
- Applications — what should happen next with active applications?
- LinkedIn Profile — what should improve in professional positioning?
- Market Insights — what is working and what should change?
- Settings & Data — preferences, backup/data controls and advanced diagnostics.

## Architectural constraints
- Repository + `.ai/` are authoritative project memory; chat is temporary.
- Human review decisions and Application state outrank capture lifecycle.
- Capture cleanup/archive must never erase pursued/reviewed/application state.
- JOLT owns deterministic capture, provenance, validation, persistence and UI; ChatGPT owns judgment-heavy reasoning.
- AI review order is source evidence -> Stage-1 hardlines -> candidate evidence -> fit -> recommendation.
- Stage-1 REJECT/MANUAL_REVIEW stops fit analysis.
- Positive AI decisions require resolved eligibility; duplicates cannot be positive.
- Missing candidate/profile evidence means unknown, not absent.
- Labs/study/certifications must not be upgraded to production experience.
- No credential storage, CAPTCHA bypass, unattended mass crawling, auto-apply or recruiter messaging.
- Production-affecting releases must retain exact-head backend/frontend, Playwright/sidebar-kanban, full-cycle, clean-install, migration-recovery, reproducible-release and Windows-script gates.

## Recent architecture remediation
- PR #464 unified discovery-batch job review with aggregate intelligence refresh.
- PR #465 added backend-owned `/api/ai-status` and removed browser-local freshness authority.
- PR #466 removed the hidden Applications -> legacy Evaluation dependency.
- PR #467 made the Unified AI Work Package the sole durable AI context authority and deprecated individual AI mutation routes.

## Immediate product direction
1. Use JOLT normally and let real search/application outcomes accumulate.
2. Continue the approved simplification sequence with **Settings & Data**, then **Applications**.
3. Keep Search Performance evidence-driven; do not restart broad search experiments without outcome evidence.
4. Complete the supervised Indeed adapter acceptance: multi-page CDP navigation and title-anchor filtering are merged through PR #491; one fresh real capture on post-#491 main is still required before calling Indeed production-accepted.
5. Keep `.ai/` and `PROJECT_MEMORY.md` synchronized when architecture or ownership changes.

## Start here
1. Read `.ai/PROJECT_STATE.json`, `.ai/KNOWN_ISSUES.md`, `.ai/OPERABILITY.md`, `.ai/ROADMAP.md` and `PROJECT_MEMORY.md`.
2. Inspect current GitHub branch/commit and open PR/issues.
3. Load only the contract/module files relevant to the active workstream.
4. Preserve the ownership and unified-intelligence rules above.
5. Verify exact-head tests/runtime before changing behavior.


## 2026-10-03 operational update
- Daily LinkedIn discovery is operating through the saved-search portfolio and frozen discovery batches.
- Discovery batch `27ddb661-98c2-4ffd-ab9e-28a07df1f377` exported 173 raw capture items, 135 canonical postings, 14 already-reviewed exclusions and a frozen 121-posting review set.
- The 121-posting Unified AI Work Package was reviewed under contract 1.2; the returned update is intended for normal UI import, with human Apply/Reject decisions remaining authoritative.
- Supervised Indeed acquisition is now a real source adapter, not a hypothetical roadmap item. PR #489 added authenticated multi-page capture, PR #490 recovers closed CDP pages and fixes launcher failure reporting, and PR #491 filters secondary action anchors from job-title discovery.
- The 2026-10-02 live Indeed run proved three-page navigation (start=0/10/20) and unique-jk deduplication, but exposed action-link contamination and stale-backend ingestion. Those defects were corrected; a fresh post-#491 live acceptance remains required.
- No open product PRs or GitHub issues remain after stale documentation PR #453 was closed as superseded.
