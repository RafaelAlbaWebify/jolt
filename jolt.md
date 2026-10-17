# JOLT — Operating Context

## SOURCE AUDIT REGISTER — 2026-10-17
- Durable component-by-component static audit: `docs/audits/component-register.md`; reviewed components, precise source findings, live-vs-static limitations and planned batches in `docs/audits/batches/`.
- Baseline `main` 27ecd6944c9cf2216cbaa6bf8884dd126c7d9f29: **178 of 333 inventoried production components (53.45%) source-audited**, not 100% JOLT operability. Do not count partial reads/tests as reviewed. Reconcile inventory/denominator as modules change.
- Batches 01–29 documented in `docs/audits/batches/`; 155 pending production components; batch 01 concerns include blind duplicate description overwrite, InfoJobs retry starvation and Jobgether JSON-LD-only extraction. Read this register before modifications; never lose unfinished findings in a chat handover.

## ACTIVE PRODUCT PRIORITY — 2026-10-17
- Deliver usable job searches from LinkedIn, Indeed, InfoJobs and Jobgether **inside JOLT**, with captured job descriptions and truthful Review Inbox entries. This objective outranks test-harness refinements and incidental refactoring.
- InfoJobs and Jobgether now have a development implementation connecting saved searches to existing supervised browser capture and provenance-checked Review Inbox import. **Not operationally accepted until latest branch/main CI and real Windows evidence.** Browser login/verification remains user-supervised; never bypass it.
- Each source must run from the same Discovery queue. Treat the presence of source adapters, mocked tests, or a "Ready" badge as insufficient proof of real portal availability.
- A source is complete only with a real portal capture, preserved job description/URL, review visibility, truthful failure reporting, no duplicate or overwritten decisions, green CI and merged changes.
- Do not spend another operator iteration refining generic acceptance tooling unless it blocks one of these concrete portal outcomes.

## EXECUTION CONTRACT — 9/10 EFFICIENCY TARGET
- Treat 9/10 as a measurable target, NOT an achieved score; assess over five successive accepted milestones. Never sacrifice source truthfulness, user data, or release safety to reduce turns.
- One user request should drive one cohesive outcome: inspect current state, implement code/tests/UI/docs, validate, repair, merge if qualified, and record evidence without routine check-in requests.
- At each chat restart, read `jolt.md`, `AGENTS.md`, `.ai/CONTEXT.md`, `.ai/PROJECT_STATE.json`, `.ai/KNOWN_ISSUES.md`, `.ai/OPERABILITY.md` and controlled roadmap; verify current main SHA, branch divergence, open PRs and exact-head checks. GitHub is durable while operator PC is off.
- Prioritize pre-PR quality gates: use `tools/dev-preflight.ps1` WHEN IMPLEMENTED; until then explicitly run Ruff lint/format, Pyright, pytest, frontend tests/build and relevant Windows/Playwright checks. Never state nonexistent scripts or checks have run.
- Fix formatter/import/type/test expectation issues on the same branch BEFORE opening a PR; branch CI green first, then one coherent PR, exact-head PR CI and safe merge. Reconcile branch divergence before PR; no parallel writes to the same file.
- Check CI at meaningful transitions, not rapid polling. Give exact active SHA checks link `https://github.com/RafaelAlbaWebify/jolt/commit/<SHA>/checks` and PR URL where available; distinguish queued/running/failed/green.
- Use production-shaped disposable Windows/SQLite regression tests when touching migration, restore, database handles or retention; require real operator acceptance where roadmap specifies it. Never mutate live database or browser state without explicit authorization.
- Design a future single-command operator acceptance runner producing a dated JSON report in Downloads, with current checkout/runtime SHA, safe read-only probes, retained record counts and failure evidence. Do not claim it exists until merged and tested.
- Keep machine-readable status authoritative by scope: legacy local-first readiness in `.ai/OPERABILITY.md` is distinct from 4-portal controlled roadmap progress. Update `.ai/PROJECT_STATE.json` only with verified acceptance/CI/merge facts; do not overwrite prior history.
- Objective metrics over five milestones: zero avoidable lint/format CI failures; <=1 operator intervention per ordinary milestone; >=90% first-PR success; >=95% regression capture for recurring known defects where measurable; 100% required evidence; zero protected-data incidents. Treat undefined baselines as unknown, not as passes.
- Operator interventions only for unavailable authenticated Windows/browser proof, sensitive approvals or business decisions. Do not request routine GitHub checking, repeated output or unnecessary cloning.
- Resume after power-off: all committed remote GitHub state persists, local uncommitted changes/SQLite remain on operator PC; cloud cannot claim live Windows acceptance when PC is off. On next session inspect GitHub, then ask for one minimal operator acceptance step only if required.

## GUARDRAILS
- Local checkout policy: ONE permanent canonical project folder; no other clone/worktree unless necessary and explicitly approved. Never force-remove/reset/clean user data.
- Preserve `AGENTS.md`, `.ai/` controls, `PROJECT_MEMORY.md`, source contracts, secrets, browser profiles, local data, backups, user decisions and applications.
- Follow `docs/operations/controlled-development-roadmap.md` fixed-weight binary per-subphase acceptance: 100% only when evidence, tests, exact-head CI, merge and required operator acceptance hold; otherwise 0%.
- Ordinary qualified development/documentation PRs may merge autonomously. Destructive, live outreach, production-data changes and irreversible operations require explicit approval.
- Use concise English. If a user's English correction is helpful, suggest a short, natural alternative without derailing engineering.

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

## STATE — 2026-10-16 HANDOVER
- Current verified `main`: `49879c7c939507b518dcd5cef1b2b41a059cc61c` (PR #587 merged; provenance-backed Market Insights unique source identities vs observations). Revalidate SHA next session.
- Phase 1 = **75%** accepted (1.1=10, 1.2=20, 1.3=25, 1.4=20). Phase 1.5=0% (weight 15), 1.6=0% (weight 10); Phase 2=0%; Phase 3=0%. No overall cross-phase completion percentage defined.
- Phase 1.4 real Windows PASS 2026-10-16: verified backup/restore, integrity, isolated migration 0030→0033, approved live 0033 migration; preserved 51 applications, 133 human decisions, 3 outcomes, 1,913 AI reviews. Supervised repeated LinkedIn evidence validated. Do not repeat this acceptance without a specific regression reason.
- Operator's last report described 296 capture runs, 6,938 capture items, 4 source identities, 9 observations. This is handover-reported, not newly inspected local database evidence.
- NEXT: Review Inbox Phase 1.5 branch `feat/phase15-review-source-history-20261016`, head `b901c656c2e16e6af3efb194dc2ae7d4228db502`; 6 commits ahead, 1 behind main when checked. Source URLs, verified identities and confirmed non-destructive duplicate links implemented in four changed files. CI green NOT confirmed; PR NOT opened. Reconcile with main, preflight, complete branch CI, open qualified PR, exact-head PR checks, merge, and collect integrated UI acceptance; only then accept 1.5.
- AFTER: Phase 1.6 integrated four-source fixture, source-truth regression, restart/retention/restore rehearsal; then Phase 2 live LinkedIn, Indeed, InfoJobs, Jobgether independently; then Phase 3 multi-source review, analytics, recovery and release sign-off.
- Efficiency implementation still pending: `tools/dev-preflight.ps1` and consolidated acceptance runner are PROPOSED deliverables, not implemented. This file establishes the workflow policy only.
