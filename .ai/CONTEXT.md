# JOLT AI Bootstrap Context

JOLT is a local-first, single-user job-search evidence, review, application-tracking, LinkedIn-profile, and market-intelligence workbench. It captures and preserves source evidence, normalizes/deduplicates opportunities, exposes structured review data, persists durable user/application state, and exchanges judgment-heavy analysis with ChatGPT through validated JSON contracts.

## Product direction
Target user: the owner/operator conducting a real job search. JOLT is now in normal production use for that search. Development should improve real operator outcomes and remove observed friction, not reopen already-certified subsystems without new evidence.

Core lifecycle:
`saved searches/manual intake -> preserved evidence -> normalized posting -> AI review exchange/import -> Review Inbox -> human decision -> durable Application -> outcome -> search/market feedback`.

Major user modules: Capture Jobs, Review Inbox, Applications, LinkedIn Profile, Market Insights, Settings & Data.

## Current production state — 2026-09-28
- Supported boundary: local-first, single-user JOLT on Windows x64.
- Production operability remains 100% inside that boundary.
- The real production LinkedIn portfolio contains 12 active searches after V1/V2/V3 search-behavior experiments and portfolio consolidation.
- Normal production job discovery is the Saved LinkedIn Searches / Discovery Batch flow.
- AI review export/import is already implemented in JOLT UI. PowerShell/API calls used during the September 27–28 audit were only an analysis shortcut, not a missing product capability.
- Recovery of stale `scheduled/running` discovery batches after backend/PC restart is merged in PR #437. Ordinary `queued` batches remain untouched.
- Search-performance funnel work is tracked as R-027 / PR #439 until merged.
- Historical experimental searches (EXP/EXP2/EXP3/HIST) are retained disabled for provenance; do not reactivate/delete them casually.
- Review Inbox human decisions and Applications remain protected durable state. Never clear or rewrite them to simplify capture experiments.

## Architectural constraints
- Repository + `.ai/` are authoritative project memory; chat is temporary.
- Human review decisions and Application state are durable and outrank capture lifecycle.
- Capture cleanup/archive must never erase pursued/reviewed/application state.
- JOLT owns deterministic capture, provenance, validation, persistence and UI; ChatGPT owns judgment-heavy reasoning.
- AI review order is source evidence -> Stage-1 hardlines -> candidate evidence -> fit -> recommendation.
- Stage-1 REJECT/MANUAL_REVIEW stops fit analysis.
- Positive decisions require resolved eligibility; duplicates cannot be positive.
- Missing candidate/profile evidence means unknown, not absent.
- Labs/study/certifications must not be upgraded to production experience.
- No credential storage, CAPTCHA bypass, unattended mass crawling, auto-apply, recruiter messaging, reactions, invitations, or account changes.
- Required merge gates: CI + Playwright acceptance + full-cycle certification, plus the production certification workflows required by the current release process.

## Product-development rule
Use JOLT normally and collect real outcome data. Do not resume broad search-keyword experimentation merely because precision can be improved theoretically. Change a saved search when:
1. it fails operationally;
2. repeated real runs show poor actionable yield; or
3. real application/interview/offer outcomes justify the change.

The qualitative product loop is now:
`search -> AI signal -> human pursue -> submitted application -> interview -> offer/outcome -> search performance`.

## Start here
1. Read `.ai/PROJECT_STATE.json`, `.ai/KNOWN_ISSUES.md`, `.ai/OPERABILITY.md`, and `.ai/ROADMAP.md`.
2. Inspect current `main`, open PRs, and exact workflow status.
3. Read `PROJECT_MEMORY.md` for durable historical invariants.
4. Load only contract/module files relevant to the active workstream.
5. Verify code/tests/runtime before changing behavior.
6. Prefer problems observed during real job-search use over speculative feature work.

Authoritative deeper references: `README.md`, `PROJECT_MEMORY.md`, `docs/domain-model.md`, `docs/automation-and-testing.md`, `.github/workflows/*`, backend `src/jolt/`, frontend `src/`.
