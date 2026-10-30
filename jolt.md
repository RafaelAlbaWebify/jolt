# JOLT — Operating Context

## CURRENT HANDOVER — 2026-10-30: REVIEW-INBOX AI IMPORT FAILURE

- The attached `JOLT_REVIEW_ONLY` export contains 300 postings and declares `classification_authority: external_ai`. All 300 `preanalysis.final_decision` values are null and `review_required` is true. This export is an AI handoff, not JOLT's final native classifier output; use persisted native evaluator records for the classifier audit.
- The first `JOLT_IMPORT_AI_REVIEW_20261030.json` import failed and rendered a wall of `[object Object]`. Source review confirmed the unified importer requires root `reviewed_at` and `review_version`; the file omitted both. It also supplied 1,186 strings under `mandatory_requirements`, while review contract 1.2 requires structured objects there.
- Additional contract conflicts required corrections beyond adding missing fields: 47 `REJECT` and 3 `MANUAL_REVIEW` records carried Stage-2 fit scores; all 24 pursue decisions had clearance marked unknown; 10 pursue decisions had a LinkedIn Remote model without official confirmation of work from Spain. The corrected copy preserves all 300 IDs, converts the 10 unresolved remote cases to conditional, removes scores blocked by Stage-1 precedence, and marks clearance clear only where the complete posting contains no clearance requirement.
- Corrected decision totals: 271 reject, 14 pursue, 15 conditional. These are ChatGPT review outcomes, not JOLT-native classifications. The corrected file passed a source-derived structural/gate preflight; it has not been imported or validated against the live database/context.
- The screenshot's error display is a separate UI defect: `frontend/src/App.tsx:errorFromResponse` treats FastAPI `detail` as a string, so a structured error array becomes `[object Object]`. No frontend fix is included in this documentation update.
- Next: import only the corrected copy after checking the package context is still current; keep the native-classifier audit separate until JOLT evaluator outputs are available. Any later import error should display individual paths/messages and must not be hidden by retrying.

## CURRENT FOLLOW-UP — MARKET INSIGHTS UI (2026-10-29)

- User confirmed [PR #695](https://github.com/RafaelAlbaWebify/jolt/pull/695) is green and merged. The compact market package was exported at 93,959 bytes and imported successfully in the desktop JOLT session.
- Screenshot acceptance then exposed desktop clipping and raw rendering of imported metadata. [PR #696](https://github.com/RafaelAlbaWebify/jolt/pull/696) addresses page scrolling, notice placement, curated market conclusions, readable skill signals, expandable recommendations, metric layout, and separate strategy/evidence dates.
- PR #696 is source-reviewed but has not yet received browser acceptance; verify by restarting the local app after merge. No tests or browser checks were run during this UI repair.

## CURRENT HANDOVER — 2026-10-29: REVIEW INBOX / MARKET INSIGHTS

**Verified GitHub status:** PR #691, #692 and #693 are merged. All eight workflows on the final #693 head (`ac1a8a21`) succeeded. These are GitHub CI results, **not** proof of deployment or real Windows/browser acceptance. The older statements below saying Delivery B was `NOT STARTED` or both screens necessarily export the same unified package are superseded by this handover.

### Shipped capability

- **#691 — Review Inbox classification-only export:** `GET /api/ai-work-package/review-export` produces `JOLT_REVIEW_ONLY.json`. Its builder omits the seven unrelated intelligence exchanges. The Review Inbox button now uses this route. The result retains the `jolt_ai_work_package` envelope; the existing `POST /api/ai-work-package/import` handles reviewed `jolt_ai_work_package_update` responses. Legacy unified export remains available for compatibility.
- **#692 — Local market statistics:** `GET /api/ai-market/automatic` calculates market indicators from persisted evidence using the optimized market-intelligence builder. It is read-only, independent of AI feedback/import, and supports validated timeframe/source-scope filters. The existing `/api/market-intelligence` endpoint remains available.
- **#693 — Automatic Market Insights UI:** `frontend/src/MarketIntelligence.tsx` fetches `/api/ai-market/automatic` when active and on refresh, alongside strategy and application data. The page displays unique roles, target roles, evaluation coverage and commonly mentioned skills. Automatic indicators are distinct from stored ChatGPT strategic conclusions. Failed automatic fetches display a nonfatal message rather than silently inventing data.

### Delivery B extension — compact strategic market export (candidate branch, not yet accepted)

- Dedicated `GET /api/ai-work-package/market-export` produces `JOLT_MARKET_STRATEGY.json` using persisted, identity-deduplicated local market aggregates. It does **not** include Review Inbox jobs, vacancy bodies, per-job candidate decisions or the seven unrelated exchanges.
- The output retains the `jolt_ai_work_package` 1.0 envelope with one `market_insights` exchange, so current `POST /api/ai-work-package/import` remains the import path. This does not claim independent market **import** yet.
- Market Insights download link targets the compact route. Its strategic recommendations are still ChatGPT-generated, not automatic.
- Evidence is aggregate, not individual vacancy provenance; do not invent individual source references. Validate exact-head CI, measured payload size and real Windows round-trip before marking accepted. Preserve legacy unified export for compatibility.

### Still outstanding — do not claim full workflow separation

- **Market Insights strategic export:** a compact independent export is implemented on this candidate branch; acceptance remains pending CI/merge and real payload-size measurements. The legacy unified export remains for compatibility.
- **Market Insights strategic import is NOT independent yet:** it still uses `/api/ai-work-package/import`; `/api/ai-market/export` and `/api/ai-market/import` are legacy deprecated endpoints, not the new target flow.
- Strategic panels such as market conclusions, skill gaps, profile actions and recommendations still require ChatGPT-generated feedback. Do not imply those panels are automatically populated by the local metrics endpoint.
- New UI metrics and earlier market view provenance use different source/aggregation concepts: clearly distinguish canonical unique roles, raw observations and evaluated observations. Avoid misleading claims of 1:1 equivalence.
- Operator Windows acceptance of the new UI and live timings is still pending. Do not infer success from CI alone.

### Next cohesive delivery

Build a **small, task-specific strategic Market Insights exchange** from retained market data and imported Review Inbox classifications, without re-exporting full Review Inbox bodies or duplicating classifications. Define a bounded/canonical sample and evidence references, version/freshness handling, complete import validation and non-destructive context/feedback writes. Update Market Insights buttons to the new strategic contract, add payload-size and no-duplicate-work regression tests, test existing unified import compatibility, and run formatter, typecheck, frontend tests/build, targeted backend tests and browser acceptance **before opening a PR**. Group related changes; do not repeat #693's serial one-assertion CI fixes.

**Relevant evidence:** https://github.com/RafaelAlbaWebify/jolt/pull/691 · https://github.com/RafaelAlbaWebify/jolt/pull/692 · https://github.com/RafaelAlbaWebify/jolt/pull/693

---

## EXECUTION METHOD V2 — EFFECTIVE 2026-10-28 (SUPERSEDES MICRO-PR WORKFLOW)

**Decision:** Stop using one PR/chat exchange per trivial code fix. Deliver **complete, demonstrable capabilities** with a frozen scope and grouped tests. This execution method overrides earlier micro-milestone recommendations in this file, while retaining all non-destructive data and release safeguards.

### Fixed definition of done — Delivery A

A closes when the following are **actually proven**, not just coded:
1. **Safe imports:** a disposable-test failure/replay matrix verifies same-payload replay, conflicting replay, failure before writes, during SQLite writes, during JSON sidecar writes, and recovery/reconciliation. Record what cannot be atomically committed across stores. Existing human decisions/applications unchanged.
2. **Processing coverage:** report per-module evidence applicability, pending/processed/error/not-applicable and provenance/version where available; missing signals must be labelled unknown, NOT inferred as completed. Reuse the existing AI status and Market observation models; add schema only when necessary and justified.
3. **One operator diagnostic:** produce a redacted single-command ZIP including DB integrity, storage, software revision, relevant processing/health counters and timing, with clear distinctions between offline checks and live/browser validation.
4. **Measured acceptance:** reproducible before/after fixture benchmark and, once at the end, one Windows operator run on a safe read-only diagnostic. Confirm CI on exact PR head, migration/restore safeguards when relevant, and update scorecard with links to real evidence.

### Batching policy

- **One execution branch/PR for the remaining coherent A capability** rather than one PR per file or one per minor test. If risk requires separation, justify the dependency in the PR description; do not open a chain of tiny documentation PRs.
- Before editing: inventory current main, pending PRs, code contracts, data/transaction boundaries and tests. Freeze files, interfaces, acceptance tests and known limitations in `docs/modernization/DELIVERY_A_ACCEPTANCE.md`. A previous merged capability must not be reimplemented.
- Implement multiple tightly related code + regression + documentation changes on that branch. Use tests and CI before asking the operator to do anything; repair formatter/lint/type failures on branch without extra chat turns.
- **No idle waiting on GitHub** when independent work is possible. CI and review proceed while non-conflicting tasks are developed. Do not merge an unverified head or overwrite another active branch.
- **Chat reporting:** one compact consolidated completion report per meaningful capability. Interrupt only for a real blocker, security approval or final operator acceptance. Avoid repeated status-only replies or speculative percentages.
- **No task creep:** classify new findings as release blocker, important follow-up, or backlog. Only blocker fixes expand the current A branch. Capture B/C/UI changes separately in backlog; do not postpone A for cosmetic or low-risk improvements.
- **Auditability:** cite PR number, commit, checks and fixture/Windows evidence; distinguish source review, CI, and real deployment. Never invent timings or claim full end-to-end safety because one narrow test passes.
- **Merge:** safe ordinary PR may merge after all required exact-head CI gates pass and checks align with acceptance. Protected data changes or live destructive work still require operator approval.

### Release plan after A

**B: Independent analysis workflow.** Task-scoped exports/imports with backwards-compatible unified mode, module-specific contracts, resumable checkpoints and completeness accounting. Ship as a cohesive workflow, not separate tooltip/API PRs.

**C: UI and operations.** Browser-tested state refresh, cleanup of duplicate mounts, retention policy/dry-run, measured performance and full operational release gate.

**Current factual position (2026-10-28):** PRs #667–#675 were reported integrated and validated in GitHub checks; #676 operator diagnostic is open with CI not yet confirmed at the moment this decision was recorded. Existing improvements are partial; do not call A complete or infer Windows operability.


## ACTIVE MODERNIZATION PROGRAM — 2026-10-28 (A → B → C)

**Scope and precedence:** This is the active cross-module reliability/efficiency program, not a replacement for the controlled portal/candidacy roadmap or protected data rules above. Preserve historical handovers as dated evidence, not current runtime truth. Prioritize any real candidate applications already approved by the operator; do not block them for speculative refactoring.

**Goal:** JOLT must capture once, account for every retained evidence item, serve each module independently, provide compact task-scoped exports to ChatGPT, safely import feedback, and retain only data that is safe to compact or remove. Reduce operator turns by batching related code, tests, docs and CI into one coherent PR per milestone where risk permits.

### Deliveries and non-negotiable acceptance

| Delivery | Scope | Acceptance gate | State |
|---|---|---|---|
| A — Baseline, integrity, processing inventory | Read-only diagnostics; storage/table/capture inventory; baseline sizes/durations; trace SQLite and JSON persistence, replay/failure behavior; processing-ledger design; remove confirmed N+1 query with parity tests | Repeatable baseline and provenance; zero mutation of live DB; real fail/replay tests using disposable fixtures; measured query counts before/after; ledger accounts for applicable/pending/processed/failed/not-applicable (if implemented) | IN PROGRESS — baseline first |
| B — Independent workflows | Task-scoped Review / Market / Skills / Profile / Applications / Quality exchanges; self-contained three-stage review protocol/checkpoints, exact coverage and schema validation, safe import; preserve existing unified mode | Review package excludes unrelated exchanges; separate Market package and view refresh; 100% IDs accounted for; stale/replay guarded; tests prove isolation and import readback | IN PROGRESS — Review-only export and automatic Market view merged (#691–#693); strategic Market exchange and full acceptance pending |
| C — UI, lifecycle, release certification | Six principal views audit, stale-state fixes, redundant UI removal, retention dry-run, safe compaction, performance and operational diagnostics | E2E routes and UI with real state where feasible; no deletion of unprocessed/sole decision evidence; restore rehearsal; measurable before/after; operator Windows acceptance where required | NOT STARTED |

**Implementation sequence and minimal-chat policy:**
1. For A, collect read-only system facts first. Make no destructive migration, cleanup, reset, live browser modification, or unsolicited application. Confirm existing schema and source of truth before adding a processing ledger; do not confuse market observation ingestion with semantic analysis.
2. Build fail/replay and protected-state regression tests against isolated SQLite/temp JSON paths; make imports preflight-validatable and idempotent. Current unified importer can commit SQLite per review and write JSON stores independently: do not claim atomicity until failure-injection tests prove safe behavior.
3. Optimize observed query bottlenecks only after correctness parity (notably Review Inbox latest verified capture selection per posting); report SQL/query counts and timings for frozen fixture.
4. In B separate **exports by task** while retaining backward-compatible unified export. Include source package ID, immutable identifiers/hashes, contract version, user-owned preferences, relevant candidate evidence, and matching review instructions. The stages Mensaje 1/2/3 are logical; allow resumable batches when corpus exceeds safe context. Do not export unrelated market/skills/application corpora merely to review jobs.
5. Processing ledger must distinguish module applicability from completion; use source ID + content hash + processor version and event/outcome. Retention MUST be dry-run-first, protect unprocessed inputs and references needed for human decisions/applications; configurable windows only after audit and operator sign-off on live destructive actions.
6. In C verify all six views and any shared UI, cross-view refresh, endpoint errors, accessibility, stale data, and expensive mounts. Capture actual browser/backend evidence; CI green is not live acceptance.
7. Each delivery: inspect -> implement cohesive branch -> targeted tests + static checks -> PR exact-head CI -> merge if green/safe -> ONE combined optional local Windows read-only acceptance script/report, if necessary. Provide consolidated result rather than asking for per-file console commands.

**Metrics/targets, NOT established achievements:** current AI export ~11.2 MB for 347 Review Inbox jobs (2026-10-28 upload; re-measure on fresh data); target Review-only ~2.5–4 MB **if zero review evidence loss**; current selected-capture loop can issue up to one query per pending posting; target one batched selection; 100% applicable records ledger-accounted; 0 duplicate review imports; 0 protected-state loss; no increase in required operator actions. Collect before/after wall time, query count, CPU/memory where available, bytes by section, data-retention candidates, import failure/retry evidence. No unmeasured speedup claims.

**Confirmed audit signals to address:** unified builder eagerly invokes seven exchange builders; Market Insights frontend and Review Inbox both link to unified export/import; Market Insights has its own view and provenance observations; SQLite and JSON feedback/context/preparation stores are separate transaction domains; Workbench keeps hidden views mounted and duplicates DataTools placements; current Review Inbox selection loops per posting. All are source-level findings, not proved user-facing failures or timed benchmarks.

**Operator report contract:** single redacted JSON artifact containing checkout/runtime SHA, schema version, database integrity, table/row/size overview, processing coverage by module when available, per-step timings, error evidence, and safe cleanup candidates. No secrets, browser profiles or raw vacancy descriptions in a diagnostics-only export. Never report live baseline from fixture or repository code.

**Progress accounting:** Mark A/B/C complete only after their entire acceptance gate passes; record partial capabilities as delivered without inflating percentage. Update this section with verified commit, PR, CI and operator evidence. Next step: merge read-only baseline tool after CI, then implement integrity tests/ledger design within A.


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

## LIVE APPLICATIONS / SEARCH INTELLIGENCE — 2026-10-25

**Immediate goal:** Begin human-approved applications today on Indeed and LinkedIn; maximize *realistically obtainable jobs*, not IT keyword agreement or capture count. The final job-selection criteria are (in order of practical relevance): likelihood of meeting mandatory requirements and being hired, actual pay, work conditions/location/contract, and career outlook. Salary missing is unknown, never zero or invented; remote labels do not prove work-from-Spain eligibility. Do not assign pseudo-probabilities of hiring.

**Transferable skills are not restricted to adjacent technical roles.** Include administrative/back office, customer service/contact center/teleoperator, order processing, logistics administration, sales support, document/data operations, and other nontechnical work alongside IT/application/industrial support. Evaluate actual job duties, qualification barriers, language, work demands, sales pressure and transport constraints. No automatic exclusion merely because a role is outside IT. Preserve the validated live preferences (Vigo vicinity, remote from Spain, permitted shifts, physical demands, acceptable contract types); fetch preferences before hard gating.

**Evidence on hand (not a new live-job availability check):** Oct 24 Indeed broad capture 200 (198 verified); Oct 25 pilot 1: 498 captured / 420 distinct / 494 verified; pilot 2: 277 captured / 169 distinct / 276 verified. Across two pilots 503 distinct Indeed identities (86 overlap), approx 501 with extracted descriptions. Additional pre-Oct-25 LinkedIn/Indeed batches and exports exist and should be considered for coverage, not silently counted as current availability. These samples are *heavily IT query-biased* and cannot establish ranking among general administrative/service roles. Existing locally produced inventory/ranking v1 is exploratory, not validated production AI output; ranking erroneously placed geographically blocked or high-skill-gap remote ads at the top. Do not apply exclusions or import human decisions from it.

**Required complete operational loop:**
1. JOLT captures independently for each platform, stores description/identity/provenance and distinguishes new vs duplicates and verified vs rejected.
2. JOLT produces *evidence-backed preliminary* eligibility, skill-transfer, pay, conditions and outlook signals, preserving unknowns and hardline conflicts.
3. Export a bounded, source-grounded AI review package, including descriptions, search provenance, human decisions/previous review and explicit uncertainty; do not strip all disqualified or nontechnical roles.
4. ChatGPT reviews the uploaded package deeply (including false negatives and nontechnical jobs), returns structured reasoned findings, conflicts, application shortlist, and better test-search URLs.
5. Import review through existing protected, idempotent AI contracts without overwriting human decisions, applications, historical evidence, or relying on fabricated eligibility.
6. Human explicitly reviews and submits applications; JOLT records application/outcome and measures unique viable leads, reply rates, quality and source/search yield. Feed outcomes back to next Indeed + LinkedIn search experiments.

**Immediate delivery order:** First shortlist and start human applications from existing verified descriptions and LinkedIn/Indeed evidence; for every shortlisted item verify live listing, exact work location, hard mandatory qualifications, pay if present, application URL and whether previously applied. Next improve existing export/review/import contracts only when a verified gap blocks feedback. Do NOT delay applying for speculative AI-scoring engine refactoring or another 200–500 capture batch. Candidate opportunities may be explored without any automated application or recruiter messaging. Capture and review on LinkedIn independently rather than assuming an Indeed listing is cross-posted.

**Search experiments:** Existing Indeed technical queries show high overlap and poor precision for MES/ERP/implementation specialty titles. Test a small, independently measured selection of IT plus genuinely nontechnical transferable families; compare *distinct, eligible, attractive vacancies and accessible applications per search*, not raw returned count. Record URL, portal, query, location, results, duplicates, actionable leads, explicit blockers and eventual applications. Avoid declaring 'best URLs' from an IT-only sample.

**Change safety:** Original Windows JOLT production checkout/backend (port 8000) is not to be reset, killed or overwritten; isolated 8018 worktree/DB reserved for tests. Latest explicitly deployed isolated-test merge on 2026-10-25: `00d479fdee029c3c3bc6a87037c6fefea1cd5ec7` (PR #650); all nine workflows green. Reverify live main/runtime SHA, branches, and current operator consent before making subsequent deployment or production database changes. Preserve older dated sections of this document as historical baselines.
