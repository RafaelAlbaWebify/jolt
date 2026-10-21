# JOLT — Operating Context

## SOURCE AUDIT REGISTER — 2026-10-17
- Durable component-by-component static audit: `docs/audits/component-register.md`; reviewed components, precise source findings, live-vs-static limitations and planned batches in `docs/audits/batches/`.
- Baseline `main` 27ecd6944c9cf2216cbaa6bf8884dd126c7d9f29: **232 of 300 non-test register entries (77.33%; source-depth verification pending); 244 of 333 total register entries (73.27%) source-audited**, not 100% JOLT operability. Do not count partial reads/tests as reviewed. Reconcile inventory/denominator as modules change.
- Batches 01–44 documented in `docs/audits/batches/`; 89 pending register entries; batch 01 concerns include blind duplicate description overwrite, InfoJobs retry starvation and Jobgether JSON-LD-only extraction. Read this register before modifications; never lose unfinished findings in a chat handover.

## OUTCOME-BASED PRODUCT PRIORITY — 2026-10-18
- The active evidence-based improvement scorecard is `docs/OUTCOME_BASELINE.md`. Sequential file review percentages are historical and are no longer a product goal. Prioritize operational safety, measured daily job-search outcomes and tested simplification. Do not claim real-portal success from CI.

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

## INDEED SEARCH A/B HANDOVER — 2026-10-18
- Real supervised Indeed search `application support` across Spain: first 3 pages yielded 18 verified jobs; expansion to 10 pages yielded 59 verified jobs with 6 additional observed-but-not-ingested warnings. Previous 18 AI reviews persisted across a restart; do not re-import past JSONs or overwrite protected human decisions.
- Search quality problem: the broad query returned largely unrelated aerospace/mechanical-maintenance jobs. An AI output that rejected all 59 should **not** be treated as authoritative or imported; correct both targeting and eligibility reasoning, distinguishing actual mandatory requirements from transferable IT/industrial support experience.
- GitHub PR #630 merged: Review Inbox distinguishes `Not a match` and `Check` rather than showing rejected jobs as conditional, and changes misleading rationale headings.
- GitHub PR #631 merged (commit `75f13da9c87d2cf79e4dd46aa6921cb18fb8030d`): `tools/run-indeed-search-ab.ps1` provides 6 supervised, independent title-vs-broad trials, with consistent search limits and evidence ZIP output. Real trial on 2026-10-18 reported application-support title 9, broad 1; IT-support title 8, broad 15; systems title 0, broad 15. Treat search relevance, remote work location, and eligibility as distinct criteria; capture counts alone are not application quality.
- PR #632 (`feat/indeed-promote-proven-searches-20261018`, head `5968b338852e7ac3df8a7cf42139e010726cfb46`) adds `tools/promote-indeed-search-ab.ps1`, opt-in dry-run-first idempotent promotion of the two better title searches; broad IT support is optional. Six reported CI workflows passed. **Confirm PR merge status before claiming availability on main**.
- Real per-vacancy descriptions and work-from-Vigo eligibility need to be rechecked before any candidate recommendation; some benchmark ZIP descriptions were replaced by `[submitted]`, so the benchmark alone is not authoritative for mandatory requirements. No applications were made.
- NEXT SESSION: verify main SHA and PR #632; merge only if outstanding and green, update canonical checkout once, run promotion dry-run then deliberate `-Apply` on operator Windows (JOLT running). Confirm 2 saved Indeed searches in Discovery and revisit verified promising postings, evaluating remote Spain eligibility, required skills and transferrable qualifications. Keep six failed-to-ingest items visible as diagnostics, not silently counted as captured. Further refine regional filters and work-model verification.
- This section is a dated addendum. Earlier 2026-10-16 SHA, phases and counts above are historical snapshots, not current authority.

## EMPLOYABILITY + AI EVIDENCE BATCH PROTOCOL — 2026-10-21

**Goal:** maximize *actionable, compatible vacancies* rather than raw capture volume. User-approved configuration (validated through the live preferences API): Vigo base, 30 km commuting boundary for onsite/hybrid, remote only if employment from Spain is permitted; 2026 Spanish full-time SMI EUR 17,094 gross/year as discovery floor (part-time prorated); EUR 45,000 target is not a rejection threshold; night, rotating and weekend shifts accepted; temporary and fixed-term accepted. Physically strenuous work is unsuitable; classify ambiguity for human review, not automatic acceptance/rejection. Commercial pressure is a ranking signal; do not infer physical demands from title alone. Existing saved preferences override fallback defaults.

**System responsibility:** JOLT performs supervised capture, provenance, canonical identity, deduplication, evidence retention, deterministic *explicit* eligibility constraints, and durable import. External AI performs source-grounded job-family, transferable-skill, physical-demand and commercial-pressure assessment. Keep official source vs portal conflicts and Spain remote eligibility explicit; missing description/evidence = uncertain, not eligible by assumption.

**Mandatory structured AI fields (additive to existing review contract):** employment_track (primary_it/bridge/unknown), physical_demand_status (compatible/incompatible/uncertain), physical_demand_evidence (list of verbatim evidence), commercial_pressure_status (low/high/uncertain), commercial_pressure_evidence (list). Legacy payloads default to unknown/uncertain. Store the list fields as JSON text in ai_reviews; verify both individual and LinkedIn batch imports, subsequent ORM/database reads, import idempotence and protection of existing applications/human decisions. An 'incompatible' physical label should be evidence-based and should not silently bypass existing review gates or rewrite historical human outcomes.

**Batch-first engineering / minimal operator interruptions:**
1. Audit repository, configuration, schemas and existing tests in one read batch; do not duplicate pre-existing components.
2. Prepare a coherent *single PR* covering code, additive Alembic migration, regression tests, templates and this operational handover. Use one branch and consolidate related changes before asking for Windows acceptance.
3. Run cheap static checks and targeted tests first. Preserve test evidence (commit SHA, exit codes, failures, coverage scope); repair related failures together. Migration-head assertions must be updated across *all* affected tests, not one at a time. Do not routinely rerun the full suite after each small fix.
4. Run full-suite QA once for a release candidate, with a saved report. If failures arise, rerun only impacted tests + relevant regression paths; rerun full suite only for a materially changed release candidate or before final release if warranted.
5. Validate schema changes on a consistent SQLite backup/copy, never on the only production copy. Record the *before* and *after* alembic revision, PRAGMA integrity_check, key row counts, and new columns. If the source is already at the target revision, the test establishes idempotence, NOT a genuine prior-version upgrade. Test old-version upgrades with a correctly versioned fixture/copy.
6. Validate the AI end-to-end with bounded representative real captured jobs (IT, bridge office, physical, ambiguous remote), verifying extract -> AI response contract -> importer -> persisted fields -> readback and protected human state. Use synthetic/frozen fixtures for deterministic CI; keep real vacancy evidence separate and do not invent job requirements.
7. Run large captures only after the pipeline has demonstrated correct eligibility semantics. Measure unique actionable leads per search and per 100 distinct postings, geo/remote verification, false positives, physical suitability, deduplication and failures; never equate verified capture with employable vacancy.
8. Provide **one copy-paste PowerShell batch** per acceptance milestone, writing a concise report (and artifacts when needed) to Downloads. Capture $LASTEXITCODE immediately; stop on failure; include commit SHA and scope. Avoid user uploads of redundant logs or 1,000-test transcripts.
9. Merge only after scoped and migration/import evidence passes. Do not claim CI/full-suite/live behavior is validated unless evidenced. Avoid destructive operations, rewriting existing human review decisions, or modifying applications.

**2026-10-20 evidence:** full-suite run at commit 33f4a59 executed 1,057 tests, 7 failures (4 old migration-head references, 2 obsolete internship rejections, 1 Market Intelligence freshness timezone). Follow-up targeted 23 tests passed at 64d0cf89. Operator SQLite copy from production showed source *already at* 20261020_0034, PRAGMA integrity_check=ok; 3,461 postings, 1,931 AI reviews, 51 applications, 133 review decisions unchanged. Existing AI reviews had only default values in new work-demand fields; this does NOT prove new AI classification. Further end-to-end AI import/readback acceptance required. PR #634 is the working change set, not merged as of this entry.
