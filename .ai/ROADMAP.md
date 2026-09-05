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
| R-007 | COMPLETE | Strict sequential per-job AI review protocol | R-006 | Stage 1 completed per vacancy before fit; no aggregation until all jobs complete | PR #378 + regression test |
| R-008 | COMPLETE | Positive eligibility/hardline importer safety gates | R-007 | pursue/strong_pursue require resolved eligibility; contradictions/duplicates rejected | PR #375/#379 tests |
| R-009 | ACTIVE | Correct deterministic geography evidence parser | R-008 | lowercase ordinary language cannot become US-state blockers; real US state locations/residency still reject | PR #380 CI + regression tests + regenerated real package |
| R-010 | ACTIVE | Real 79-job sequential review/import acceptance | R-009 | fresh package from corrected runtime; all 79 reviewed exactly once; importer accepts update; top survivors manually rechecked | capture/package IDs, import receipt, spot checks |
| R-011 | ACTIVE | LinkedIn AI round-trip status/receipt UX | R-006 | profile freshness and successful imports remain visibly auditable after navigation/reload | PR #376 green gates + runtime acceptance |
| R-012 | ACTIVE | LinkedIn Connections virtualized capture coverage | R-002 | nested scrolling advances unique contacts; partial vs bounded-complete quality is explicit | PR #377 green gates + real capture |
| R-013 | NEXT | Runtime staleness/version visibility | R-001 | UI/API exposes running commit/version and warns when local runtime is behind checked-out repository | automated test + local update/restart acceptance |
| R-014 | NEXT | External-beta operability pass | R-010,R-011,R-012,R-013 | clean setup, startup, real capture, persistence, AI round trip, recovery, exports all pass on supported Windows machine with no P0/P1 blocker | OPERABILITY checklist + dated evidence |
| R-015 | NEXT | Real-prospect readiness | R-014 | repeated real workflow is reliable enough to use on live opportunities without manual repair of internal state | full gate in OPERABILITY.md |
| R-016 | LATER | Indeed source adapter | stable capture abstraction | source-specific adapter preserves same evidence/provenance contracts | tests + supervised real capture |
| R-017 | LATER | InfoJobs source adapter | stable capture abstraction | same as R-016 | tests + supervised real capture |
| R-018 | OPTIONAL | Multi-user/SaaS architecture | product decision | explicit business requirement exists; auth/tenancy/security architecture approved | ADR before implementation |
| R-019 | REJECTED | Auto-apply/recruiter messaging/unattended mass crawling | none | intentionally out of product scope unless product boundaries are explicitly changed | decision ledger |
| R-020 | REJECTED | Local deterministic engine replacing ChatGPT for judgment-heavy career reasoning | none | keep deterministic code for validation/provenance only | PROJECT_MEMORY + decisions |

## Immediate sequence
1. Finish R-009.
2. Repeat R-010 from the same stored 79-job capture; do not recapture unless source evidence itself is invalid.
3. Resolve R-011 and R-012 with exact PR-head gates.
4. Implement R-013.
5. Run R-014 and only then reassess operability percentages/readiness flags.