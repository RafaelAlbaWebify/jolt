# JOLT — Operating Context

## GUARDRAILS
- Respond in concise, natural English; prioritize verified results and actionable next steps. When my English could sound more natural to a native speaker, suggest one concise correction and explain why in a short paragraph.
- At the start of a new chat, read this file, `AGENTS.md`, and the authoritative `.ai/` control files; verify GitHub branch, latest commit, open PRs and CI.
- “Continue” means execute the next concrete task, not merely propose it; investigate, edit, validate and fix autonomously.
- Preserve `AGENTS.md`, `.ai/CONTEXT.md`, `.ai/PROJECT_STATE.json`, `.ai/KNOWN_ISSUES.md` and `.ai/OPERABILITY.md`; this concise file is an entry point, not their replacement.
- Distinguish implemented, tested, CI-pending and merged. Never claim operational acceptance from fixtures or CI alone.
- Protect SQLite, user decisions, applications, source evidence, secrets, browser profiles, backups and local installations.
- Never delete records, alter production data, start live outreach or merge important branches into `main` without explicit approval.
- Follow `AGENTS.md` pre-PR gates: develop a coherent outcome, validate branch CI, inspect Ruff/format/Pyright/pytest, then open a PR.
- Report a direct GitHub PR link after meaningful updates so CI and approval status remain visible.
- Keep this file roughly 40–60 lines; replace stale facts, do not append a changelog.
- Follow `docs/operations/controlled-development-roadmap.md`; `EA` lists all numbered subphases with fixed weights.
- Roadmap completion is binary per subphase: 100% only after acceptance evidence, green exact-head CI and verified merge; otherwise 0%.
- Compute each phase's progress from fixed subphase weights; keep operational readiness separate from development completion.

## PROJECT
- Purpose: local-first, single-user Windows evidence workbench for job discovery, human review, applications, LinkedIn profile and market intelligence; ChatGPT handles judgment-heavy analysis.
- Repository: `RafaelAlbaWebify/jolt`. Target branch: `main`. Documentation work: `docs/jolt-controlled-development-20261016`; PR pending creation.
- Existing repository authority: `AGENTS.md`, `.ai/` files, `PROJECT_MEMORY.md`, domain contracts. Historical `docs/roadmap.md` is not replaced.
- Backend: Python 3.12, FastAPI/Pydantic, SQLAlchemy/SQLite, Alembic; `backend/src/jolt/`; uv, pytest, Ruff, Pyright.
- Frontend: React/TypeScript/Vite, `frontend/src/`; Vitest/RTL; Playwright and GitHub Actions for UI/full-cycle validation.
- Capture sources: LinkedIn, Indeed, InfoJobs, Jobgether; independently supervised portal capture; Adzuna removed from active catalog.
- Canonical evidence: capture runs/items, source documents, Postings, portal identities, confirmed non-destructive duplicate links, AI review and application records.
- Local startup: `./tools/start-jolt.ps1`; stop: `./tools/stop-jolt.ps1`; diagnostics: `./tools/validate-jolt.ps1`.
- Backend checks (from `backend/`): `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run pytest`.
- Frontend checks (from `frontend/`): `npm test`, `npm run build`. CI: `.github/workflows/`.
- Real portal credentials, work-from-Spain eligibility and actual user acceptance cannot be inferred from automated tests.

## STATE
- Audit baseline: 2026-10-16 `main` at `f5f89e2937221eb01db6f74a231a887b192f03c6` (PR #578 merged); eight reported main check-runs succeeded.
- Existing core local-first product has prior bounded real Windows acceptance; this does NOT establish current four-source end-to-end readiness.
- Merged source work: normalized offer hand-off, cross-portal duplicate assessment, durable portal identities, live LinkedIn/Indeed registry, candidate API, operator-confirmed non-destructive links (PRs #573–#578).
- Existing InfoJobs/Jobgether supervised promotion is evidence-gated; metadata observation does not prove a verified description or Spain eligibility.
- Open PR #572: `feat/infojobs-one-command-20261015`, draft, latest inspected head `a7030143e93ea1f6e34455274e382e6446005c5e`; backend CI failing.
- No independent local Windows acceptance of the expanded four-portal workflow has been verified in this audit.
- Roadmap baseline: Phase 1.1–1.3 merged and CI-validated; 1.4–1.6 remain unaccepted under binary completion rules.
- NEXT: finish documentation PR checks and obtain approval before merging the controlled-development files into `main`.
- AFTER: diagnose PR #572 backend failures; then implement 1.4 source observation history and 1.5 portal/Market Insights visibility, with new acceptance tests.
- After this documentation PR is merged, replace the baseline/head and active-PR entries above with newly verified facts.
