# JOLT AI Bootstrap Context

JOLT is a local-first, single-user job-search evidence, review, application-tracking, LinkedIn-profile, and market-intelligence workbench. It captures and preserves source evidence, normalizes/deduplicates opportunities, exposes structured review data, persists durable human/application state, and exchanges judgment-heavy analysis with ChatGPT through validated JSON contracts.

## Product direction
Target user: the owner/operator conducting a real job search.

Current normal workflow:
`Run saved searches -> export only new jobs -> ChatGPT review -> import reviewed jobs -> Review Inbox human decision -> Applications -> interview/outcome -> search performance feedback`.

Major modules: Capture Jobs, Review Inbox, Applications, LinkedIn Profile, Market Insights, Settings & Data.

## Current production state — 2026-09-29
- Supported boundary: local-first, single-user JOLT on Windows x64.
- Production operability remains 100% within that boundary.
- 12 active production LinkedIn searches are in normal use after controlled V1/V2/V3 search experiments and portfolio consolidation.
- Search Performance is merged and measures saved-search performance from capture through AI signal, human pursue, application, interview and offer outcomes.
- Interrupted persisted `scheduled/running` discovery batches are reconciled safely on backend restart; normal queued batches remain untouched.
- AI review export/import already exists in the UI. PowerShell/API use during the September audit was an analysis shortcut, not a missing product capability.
- UX stabilization phases 1–6 are merged through PR #452:
  - operator-facing language and safer destructive actions;
  - simpler Applications and Settings workflows;
  - simplified application document/CV attachment;
  - remaining internal copy removed from primary paths;
  - stage/outcome actions simplified;
  - keyboard/focus behavior hardened.
- Application documents are physically stored in JOLT. Non-success final outcomes purge stored file bytes; accepted offers retain them; hiding/archiving does not purge them.
- New applications use Documents as the primary CV source. Legacy `resume_used` values remain read-only historical context.
- Historical EXP/EXP2/EXP3/HIST searches remain disabled for provenance; do not casually reactivate/delete them.
- Human Review Inbox decisions and Application state are durable/protected and must never be rewritten to simplify capture or cleanup.

## Architectural constraints
- Repository + `.ai/` are authoritative project memory; chat is temporary.
- Human review decisions and Application state outrank capture lifecycle.
- Capture cleanup/archive must never erase pursued/reviewed/application state.
- JOLT owns deterministic capture, provenance, validation, persistence and UI; ChatGPT owns judgment-heavy reasoning.
- AI review order is source evidence -> deterministic hardlines -> candidate evidence -> fit -> recommendation.
- Positive recommendations require resolved eligibility; duplicates cannot be positive.
- Missing candidate/profile evidence means unknown, not absent.
- Labs/study/certifications must not be upgraded to production experience.
- No credential storage, CAPTCHA bypass, unattended mass crawling, auto-apply, recruiter messaging, reactions, invitations, or account changes.
- Required merge gates for production-affecting work: CI, Playwright acceptance, Full-cycle Playwright certification, Production clean-install certification, Migration recovery certification, and Reproducible release certification.

## Product-development rule
Use JOLT normally and let real workflow friction/outcomes drive changes.

Do not restart broad keyword experiments merely because theoretical precision can improve. Change a saved search only when:
1. it fails operationally;
2. repeated real runs show poor actionable yield; or
3. real application/interview/offer outcomes justify the change.

The qualitative feedback loop is:
`search -> AI signal -> human pursue -> submitted application -> interview -> offer/outcome -> search performance`.

## Start here
1. Read `.ai/PROJECT_STATE.json`, `.ai/KNOWN_ISSUES.md`, `.ai/OPERABILITY.md`, and `.ai/ROADMAP.md`.
2. Inspect current `main`, open PRs, and exact workflow status.
3. Read `PROJECT_MEMORY.md` for durable invariants.
4. Load only contract/module files relevant to the active workstream.
5. Verify code/tests/runtime before changing behavior.
6. Prefer problems observed during real job-search use over speculative feature work.

Authoritative deeper references: `README.md`, `PROJECT_MEMORY.md`, `docs/domain-model.md`, `docs/automation-and-testing.md`, `.github/workflows/*`, backend `src/jolt/`, frontend `src/`.
