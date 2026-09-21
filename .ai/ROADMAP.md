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
Production certification is complete for the supported local-first single-user Windows boundary.

Future work is optional/product expansion rather than a blocker:
1. Add Indeed adapter when prioritized.
2. Add InfoJobs adapter when prioritized.
3. Revisit multi-user/SaaS architecture only if the product boundary changes.
4. Re-run the production certification suite for every release that changes runtime support, migrations, LinkedIn capture behavior, or release packaging.
