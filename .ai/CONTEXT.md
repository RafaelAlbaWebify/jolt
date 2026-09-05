# JOLT AI Bootstrap Context

JOLT is a local-first, single-user job-search evidence, review, application-tracking, LinkedIn-profile, and market-intelligence workbench. It captures and preserves source evidence, normalizes/deduplicates opportunities, exposes structured review data, persists durable user/application state, and exchanges judgment-heavy analysis with ChatGPT through validated JSON contracts.

## Product direction
Target user: the owner/operator conducting a real job search. Current use is personal production-like use rather than a multi-tenant SaaS. JOLT should reduce bad applications and repeated manual review while preserving provenance and human control.

Core lifecycle:
`capture/manual intake -> preserved evidence -> normalized posting -> Review Inbox -> human/AI-assisted decision -> durable Application -> outcome -> market/strategy feedback`.

Major user modules: Capture Jobs, Review Inbox, Applications, LinkedIn Profile, Market Insights, Settings & Data.

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
- No credential storage, CAPTCHA bypass, unattended mass crawling, auto-apply, or recruiter messaging.
- Required merge gates: CI + Playwright acceptance + full-cycle Playwright certification green for the exact PR head.

## Current milestone
Stabilize the end-to-end real job capture -> unified AI work package -> sequential per-job review -> validated import loop, then finish remaining LinkedIn/AI UX reliability work.

## Current blockers
- PR #380 fixes a deterministic geography false-positive where lowercase words such as `de` could be interpreted as US state abbreviations. It is not yet on `main` at the time this control layer is created.
- PR #376 AI round-trip UX and PR #377 LinkedIn Connections coverage remain open and require exact-CI verification before merge.
- Fresh end-to-end acceptance must be repeated after geography-parser correction before declaring the review loop fully verified.

## Start here
1. Read `.ai/PROJECT_STATE.json`, `.ai/KNOWN_ISSUES.md`, `.ai/OPERABILITY.md`, `.ai/ROADMAP.md`.
2. Inspect `git status`, branch and commit.
3. Read `PROJECT_MEMORY.md` for durable historical invariants.
4. Load only the contract/module files relevant to the active workstream.
5. Verify code/tests/runtime before changing behavior.

Authoritative deeper references: `README.md`, `PROJECT_MEMORY.md`, `docs/domain-model.md`, `docs/jolt-architecture-audit-20260729.md`, `docs/automation-and-testing.md`, `.github/workflows/*`, backend `src/jolt/`, frontend `src/`.