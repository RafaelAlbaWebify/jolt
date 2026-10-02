# JOLT Roadmap

Status values: COMPLETE = acceptance evidence exists; ACTIVE = current work; NEXT = immediate queue; LATER = planned; OPTIONAL = non-blocking; REJECTED = deliberately out of scope.

| ID | Status | Description | Dependencies | Acceptance criteria | Evidence required |
|---|---|---|---|---|---|
| R-001 | COMPLETE | Local-first FastAPI/React application with SQLite/Alembic persistence | none | backend/frontend start, persisted data survives restart | source, migrations, launcher, tests |
| R-002 | COMPLETE | Manual opportunity intake and supervised LinkedIn capture with evidence/provenance | R-001 | real capture produces verified items and preserved source evidence | capture run + artifacts + tests |
| R-003 | COMPLETE | Review Inbox with separate human decision state | R-002 | pending items visible; classified items leave pending inbox without losing durable state | API/UI regression tests |
| R-004 | COMPLETE | Durable Applications lifecycle | R-003 | pursue creates/retains application; archive/cleanup cannot erase application history | application-index + cleanup regressions |
| R-005 | COMPLETE | Market Intelligence evidence aggregation | R-002 | completed captures contribute to bounded evidence corpus and AI exchange | API tests + exported package |
| R-006 | COMPLETE | Unified ChatGPT work-package round trip architecture | R-002,R-003,R-005 | one package exports current evidence/sections; returned package is schema-validated and imported | exporter/importer tests |
| R-007 | COMPLETE | Strict sequential per-job AI review protocol | R-006 | Stage 1 completed per vacancy before fit; no aggregation until all jobs complete | PR #378 + regression tests |
| R-008 | COMPLETE | Positive eligibility/hardline importer safety gates | R-007 | pursue/strong_pursue require resolved eligibility; contradictions/duplicates rejected | PR #375/#379 tests |
| R-009 | COMPLETE | Correct deterministic geography evidence parser | R-008 | lowercase ordinary language cannot become US-state blockers; real US state locations/residency still reject | PR #380 exact green gates + regression tests |
| R-010 | COMPLETE | Real 79-job sequential review/import acceptance | R-009,R-021 | fresh package from corrected restarted runtime; all 79 reviewed exactly once; importer accepts update; top survivors manually rechecked | capture/package IDs, import receipt, source spot checks |
| R-011 | COMPLETE | Durable AI round-trip status/receipt UX | R-006 | profile freshness and successful imports remain visibly auditable after navigation/reload | PR #382 exact green gates |
| R-012 | COMPLETE | LinkedIn Connections virtualized capture coverage | R-002 | nested scrolling advances unique contacts; partial vs bounded-complete quality is explicit | PR #377 exact green gates complete; future live Connections run still required for live-site confirmation |
| R-013 | COMPLETE | Runtime staleness visibility | R-001 | UI compares process-loaded revision with checkout revision and visibly blocks operator workflow when stale | PR #384 exact green gates; local acceptance required as part of R-010 |
| R-014 | COMPLETE | External-beta operability pass | R-010,R-011,R-013,R-021 | clean startup, corrected real AI round trip and no unresolved beta-critical P0/P1 blocker | OPERABILITY checklist + dated evidence |
| R-015 | COMPLETE | Real-prospect readiness | R-014 | two consecutive real workflows plus persistence, recovery and source-audit gates pass without internal repair | full gate in OPERABILITY.md |
| R-016 | LATER | Indeed source adapter | stable capture abstraction | source-specific adapter preserves same evidence/provenance contracts | tests + supervised real capture |
| R-017 | LATER | InfoJobs source adapter | stable capture abstraction | same as R-016 | tests + supervised real capture |
| R-018 | OPTIONAL | Multi-user/SaaS architecture | product decision | explicit business requirement exists; auth/tenancy/security architecture approved | ADR before implementation |
| R-019 | REJECTED | Auto-apply/recruiter messaging/unattended mass crawling | none | intentionally out of product scope unless product boundaries are explicitly changed | decision ledger |
| R-020 | REJECTED | Local deterministic engine replacing ChatGPT for judgment-heavy career reasoning | none | keep deterministic code for validation/provenance only | PROJECT_MEMORY + decisions |
| R-021 | COMPLETE | Exact completeness enforcement for AI review contract 1.1 | R-007,R-008 | importer rejects any returned posting set that is not exactly the capture posting set before writing review rows | PR #385 CI 1353 + Playwright 627 + full-cycle 550 + regression tests |
| R-022 | COMPLETE | Backup/restore active-schema rehearsal | R-014 | create, verify and restore a dated backup without modifying the live database; restored database passes integrity/schema verification | CLI output + manifest + restored test target evidence |
| R-023 | COMPLETE | Unified release/version authority | R-001 | package, FastAPI health and runtime identity derive from one release-version source | tests + exact merge gates |
| R-024 | COMPLETE | Production environment/release certification | R-015,R-022,R-023 | second-environment clean install, security/privacy review, recovery policy and reproducible release all pass | PRs #403/#404/#406/#407/#408 + dated real-site LinkedIn acceptance + exact final main release gates |

## Immediate sequence
Production certification remains complete for the supported local-first single-user Windows boundary.

Normal product operation now follows one consolidated intelligence loop:
1. Run the production saved-search portfolio in Capture Jobs.
2. Download the batch-scoped Unified AI Work Package.
3. Review the frozen new-job set with ChatGPT while refreshing stale aggregate intelligence in the same package.
4. Import the reviewed update once; Review Inbox plus eligible Market/Search/Application/Profile intelligence are refreshed together.
5. Use backend `/api/ai-status` as the freshness authority.
6. Use the simplified Settings & Data and Applications surfaces in production and record concrete friction before changing them again.
7. Add Indeed/InfoJobs only when they materially improve the real workflow; no additional product milestone is currently required for operability.

## R-025 — LinkedIn Search Portfolio and Discovery Batch — COMPLETE
Goal: replace repeated one-search-at-a-time operator work with one saved multi-search discovery action while preserving per-search provenance and the certified capture engine.

Authoritative implementation roadmap: `docs/LINKEDIN_SEARCH_PORTFOLIO_ROADMAP.md`.

Current phase: COMPLETE. Phases 1–5 are merged and the real authenticated Windows acceptance passed on 2026-09-24.

Completion evidence: main `1157942fec504b3d41c6371046ae04afc8111709` passed all six push certification workflows. Real Discovery Batch `02c529d0-bae8-4cc1-8288-a7575146b515` completed 2/2 saved searches sequentially, captured/verified 50/50 jobs, produced a frozen 47-posting review set after excluding 3 already-reviewed postings, imported one consolidated 47-job ChatGPT review, and preserved state across a full JOLT restart.


## R-026 — Discovery restart recovery — COMPLETE
PR #437 safely reconciles scheduled/running discovery work after backend restart while leaving queued work untouched.

## R-027 — Saved-search performance funnel — COMPLETE
PR #439 links saved searches to captured jobs, AI signal, human decision, application, interview and offer outcomes so search tuning can use real conversion evidence.

## R-028 — Daily operator UX stabilization — COMPLETE
PRs #442, #447, #448, #449, #450 and #452 simplified operator language, dangerous actions, Applications/document handling, stage/outcome actions and keyboard/focus behavior. Issue #441 closed completed on 2026-09-30.

## R-029 — Production density + live UI audit — COMPLETE
PRs #454–#459 added the read-only live Playwright audit and fixed real viewport density/scroll behavior without weakening the 1680x945 certification.

## R-030 — Review Inbox decision workspace — COMPLETE
PRs #460–#462 introduced split-view review, functional Overview/Fit/Details panes and the simplified human decision model: Apply, Reject, or leave pending.

## R-031 — Market Insights operator dashboard — COMPLETE
PR #463 reorganized Market Insights around current KPIs, market signals, next actions and drill-down tabs while preserving evidence/freshness semantics.

## R-032 — Unified intelligence architecture remediation — COMPLETE
PRs #464–#467 close the architecture-audit gaps:
- discovery-batch review and aggregate intelligence refresh share one Unified AI Work Package;
- backend `/api/ai-status` owns intelligence freshness;
- Applications remain visible without legacy Evaluation rows;
- only the Unified AI Work Package may persist durable global AI context;
- individual exchanges and standalone legacy review/preparation routes are deprecated compatibility/diagnostic surfaces.

Acceptance evidence: PR #467 exact head `57ebc6529a3da8d50e987e6b1ad7f97ae6de00d6` passed backend, frontend rerun, Playwright/sidebar-kanban, full-cycle, clean-install Windows, migration recovery, reproducible release and Windows scripts before merge as `98953f63f7e836f100a6ef5f00c3ac5399a649f6`.


## R-033 — Project-control architecture synchronization — COMPLETE
PR #468 synchronized the repository-authoritative control files with the unified intelligence architecture established by PRs #464–#467.

## R-034 — Settings & Data daily-use simplification — COMPLETE
PR #469 made backend-owned intelligence status the primary Settings surface and moved deliberate full-strategy refresh plus legacy compatibility exports/imports into Advanced.

## R-035 — Applications operational views — COMPLETE
PR #470 added the compact Active / Interviewing / Offers / Overdue scorecard and replaced the former density toggle with Board/List views while preserving application lifecycle, stage movement, documents, contacts, tasks, interviews and outcomes.

Acceptance evidence: PR #470 exact head `8941ce34867ae2884f8a8f0917d288633c5c5ca3` passed backend, frontend, Playwright/sidebar-kanban, full-cycle, clean-install Windows, migration recovery, reproducible release and Windows scripts before squash merge as `0f252f4ec7e17dc29e31bed71a0bd86e23d18da5`.

## Current product-development posture
There is no pending operability milestone inside the certified local-first single-user Windows boundary. Normal job-search use is the primary next activity. Further product work should be triggered by observed workflow friction, a demonstrated source-coverage need, or an explicit compatibility/removal decision rather than speculative feature expansion.


## 2026-10-03 source-coverage extensions

| ID | Status | Description | Dependencies | Acceptance criteria | Evidence required |
|---|---|---|---|---|---|
| R-026 | COMPLETE | LinkedIn daily saved-search discovery + frozen unified AI batch review in normal production use | R-025 | multi-search run completes, canonical deduplication produces frozen review set, one Unified AI Work Package round trip is importable | real discovery batch + package/import evidence |
| R-027 | ACTIVE | Supervised authenticated Indeed source adapter | R-002, R-026 | 3+ pages navigate in one persistent session; only real job-title anchors are discovered; jk deduplication/provenance persist; current backend ingests package successfully | fresh post-#491 real ZIP + API result + exact-head gates |
