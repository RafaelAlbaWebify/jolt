# JOLT AI Bootstrap Context

JOLT is a local-first, single-user job-search workbench for real operator use on Windows. It captures jobs, preserves source evidence, imports validated ChatGPT reviews, keeps human decisions durable, tracks applications and outcomes, maintains LinkedIn-profile evidence, and turns retained job-search data into market feedback.

## Normal operator loop

`Capture Jobs -> export new jobs for review -> ChatGPT -> import reviewed jobs -> Review Inbox -> human decision -> Applications -> outcomes -> Search Performance / Market Insights`.

AI review export/import is already implemented in the JOLT UI. PowerShell/API calls used during the September audit were only an analysis shortcut.

Primary workspaces:
- Capture Jobs
- Review Inbox
- Applications
- LinkedIn Profile
- Market Insights
- Settings & Data

## Current production state — 2026-09-29

- Supported boundary: local-first, single-user Windows x64.
- Production operability: 100% inside that boundary.
- Real job search is active; development must not mutate the operator's production DB.
- Production LinkedIn portfolio: 12 active saved searches. EXP/EXP2/EXP3/HIST searches are retained disabled for provenance.
- Broad V1/V2/V3 search experiments are finished. Do not restart them without new real-use evidence.
- PR #437: stale scheduled/running discovery recovery merged.
- PR #439: saved-search performance funnel merged.
- PR #443: real application-document storage/retention fix merged.
- UX stabilization merged: #442, #447, #448, #449.
- UX finalization is limited to #450 (Applications actions) and #451 (keyboard/focus) until their exact heads certify.
- Historical/superseded PRs have been closed; only current work should remain open.

## Durable product invariants

- Human review decisions and Application state outrank capture/search-run lifecycle.
- Cleanup/archive must never erase reviewed/pursued/application state.
- Documents are the primary source of truth for the actual CV/supporting file used for a new application. Legacy `resume_used` remains historical context only.
- A non-success final outcome purges stored application-document bytes; `offer_accepted` retains them. Hide/archive is reversible and does not purge.
- Human decisions use user-facing labels in UI while backend enums remain stable.
- Search-performance analytics are descriptive; JOLT must not automatically disable/rank searches or make human decisions.
- Overlapping searches may receive multi-touch credit for the same canonical posting; do not interpret this as exclusive causality.
- LinkedIn account interaction remains read-only: no messaging, reactions, invitations, account edits, auto-apply, CAPTCHA bypass or unattended mass crawling.
- ChatGPT owns judgment-heavy reasoning. JOLT owns deterministic validation, provenance, persistence, contracts and UI.
- Missing candidate/profile evidence means unknown, not absent.
- Labs/study/certifications must not be upgraded to production experience.

## Development rule

The product is operational. Improve it from real operator friction and outcome data, not speculative feature expansion.

Before changing behavior:
1. Inspect current `main`, open PRs and exact workflow status.
2. Read `.ai/PROJECT_STATE.json`, `.ai/KNOWN_ISSUES.md`, `.ai/OPERABILITY.md`, `.ai/ROADMAP.md`, and `PROJECT_MEMORY.md`.
3. Preserve human/application state and the production DB.
4. Work in an isolated branch/PR.
5. Require all six gates on the exact PR head before merge:
   - CI
   - Playwright acceptance
   - Full-cycle Playwright certification
   - Production clean-install certification
   - Migration recovery certification
   - Reproducible release certification
6. Prefer real operator problems over new features.

## Immediate direction

Finish the bounded UX stabilization work, synchronize project control, then return JOLT to normal job-search use. Future UX/search changes should be driven by observed problems or funnel outcomes.

Authoritative deeper references: `README.md`, `PROJECT_MEMORY.md`, `docs/domain-model.md`, `docs/automation-and-testing.md`, `.github/workflows/*`, backend `src/jolt/`, frontend `src/`.
