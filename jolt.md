# JOLT — Operating Context

## GUARDRAILS
- Local checkout policy: maintain ONE permanent repository folder per project (the canonical main working directory). Do not create another clone, worktree, or PR-specific folder unless strictly necessary AND explicitly approved by the user beforehand. Prefer branches and CI on GitHub for isolated development.
- Temporary checkout lifecycle: document its reason and path, preserve local data and uncommitted changes, and remove it promptly once its approved purpose ends. Verify no orphan folders/worktrees remain. Never force-remove, reset, or clean user data.
- Respond in concise, natural English; prioritize verified results and actionable next steps. When my English could sound more natural to a native speaker, suggest one concise correction and explain why in a short paragraph.
- At the start of a new chat, read this file, `AGENTS.md`, and the authoritative `.ai/` control files; verify GitHub branch, latest commit, open PRs and CI.
- “Continue” means execute the next concrete task, not merely propose it; investigate, edit, validate and fix autonomously.
- Preserve `AGENTS.md`, `.ai/CONTEXT.md`, `.ai/PROJECT_STATE.json`, `.ai/KNOWN_ISSUES.md` and `.ai/OPERABILITY.md`; this concise file is an entry point, not their replacement.
- Distinguish implemented, tested, CI-pending and merged. Never claim operational acceptance from fixtures or CI alone.
- Protect SQLite, user decisions, applications, source evidence, secrets, browser profiles, backups and local installations.
- Merge ordinary development and documentation PRs into `main` autonomously after required exact-head CI passes, mergeability and acceptance are verified; no separate approval needed. Still request explicit approval for destructive actions, production-data changes, live outreach or other high-risk irreversible operations.
- Follow `AGENTS.md` pre-PR gates: develop a coherent outcome, validate branch CI, inspect Ruff/format/Pyright/pytest, then open a PR.
- EVERY development/CI update must include a clickable, direct GitHub checks URL for the exact active commit (`https://github.com/RafaelAlbaWebify/jolt/commit/<SHA>/checks`), showing live yellow/green/red results; also link the PR when it exists. Never leave the operator waiting without a checkable URL, including before PR creation.
- Keep this file roughly 40–60 lines; replace stale facts, do not append a changelog.
- Follow `docs/operations/controlled-development-roadmap.md`; `EA` lists all numbered subphases with fixed weights.
- Roadmap completion is binary per subphase: 100% only after acceptance evidence, green exact-head CI and verified merge; otherwise 0%.
- Compute each phase's progress from fixed subphase weights; keep operational readiness separate from development completion.

## PROJECT
- Purpose: local-first, single-user Windows evidence workbench for job discovery, human review, applications, LinkedIn profile and market intelligence; ChatGPT handles judgment-heavy analysis.
- Repository: `RafaelAlbaWebify/jolt`. Target branch: `main`. Operating context and controlled roadmap merged via PR #579; develop on short-lived branches and merge green PRs into `main` autonomously.
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
- 2026-10-16 Phase 1.4 operator evidence PASS: isolated database backup, verified restore, SQLite integrity, schema migration 0030→0033, and unchanged owned records.
- Approved live database migration confirmed schema `20261016_0033`, integrity `ok`, 51 applications, 133 human review decisions, 3 outcomes, 1,913 AI reviews, 6,929 legacy capture items and 293 legacy runs preserved.
- First real supervised LinkedIn capture: 294 total runs, 6,932 items, 3 source identities and 3 immutable occurrence observations; second capture: 295 runs, 6,935 items, same 3 identities, 6 observations, all 3 seen across multiple runs. 51 applications and 133 human review decisions unchanged.
- Phase 1.4 accepted: 20% fixed weight; Phase 1 now 75% (1.1–1.4). Phase 1.5 (15%) and 1.6 (10%) remain 0%.
- Provenance implementation merged via PRs #580–#583. Real-Windows SQLite cleanup fixes via PRs #584 and #585, each with 11/11 checks green. Exact PR #585 head checks: https://github.com/RafaelAlbaWebify/jolt/commit/bd534d667e67690da95a6b4643bac33867ed3102/checks .
- Dry-run legacy backfill found 0 eligible and 6,710 ineligible; no historical receipt fabrication or live backfill performed. Source-history tables began empty after migration; the verified fresh captures populate them.
- NEXT: Phase 1.5 — add trustworthy source URL/identity/duplicate link visibility to human review and provenance-backed, de-duplicated Market Insights populations; test backend, frontend and Playwright before operator acceptance.
- AFTER: Phase 1.6 four-source fixture, restart/retention/restore chain; Phase 2 independently accepts live operational behavior for each portal.
