# JOLT — Controlled Development Roadmap

Status: baseline established 2026-10-16 against `main` `f5f89e2937221eb01db6f74a231a887b192f03c6`.
This roadmap controls the **current multi-source expansion**, not a retroactive recertification of JOLT's previously accepted LinkedIn/local workflow. Keep `AGENTS.md`, `.ai/`, and `docs/roadmap.md` intact.

## Counting rules

- A subphase is **100% merged completion** only if its acceptance criteria have repository evidence, required tests passed, exact-head CI passed, and the implementation was merged into the agreed `main` target. Otherwise it is **0%**; record `implemented`, `tested`, `CI pending`, and `merged` separately.
- Every phase's percentage is the **sum of the fixed weights of its completed subphases**. No arbitrary partial percentages. No overall percentage spanning distinct phases unless separate cross-phase weights are explicitly approved.
- Existing independently accepted features are not counted twice. PR counts, documentation changes and CI alone do not establish operational readiness; real portal Windows acceptance is independently gated.
- Weights and IDs are frozen for this baseline. Changes require a documented scope-change approval, including the previous and replacement weights, rationale and acceptance impacts.
- Work in coherent small PRs; follow `AGENTS.md` branch CI preflight, and autonomously merge green, qualified PRs into `main` without separate approval. Explicit approval remains necessary for destructive, production-data, live-outreach or high-risk irreversible actions. Never infer auth, employment eligibility, browser safety or source fidelity from mocks.

## Phase 1 — Unified multi-source contract, identity and provenance

| ID | Subphase | Weight | Merged completion | Acceptance and evidence |
|---|---|---:|---:|---|
| 1.1 | Source and model audit | 10% | **100%** | Current four-source boundaries and removal of active Adzuna catalog documented; merged #573 and green exact-head CI. |
| 1.2 | Normalized offer contract | 20% | **100%** | Typed `NormalizedJobOffer` for four source adapters, strict verification/provenance distinctions and fixture tests; merged #573 and green exact-head CI. |
| 1.3 | Cross-portal duplicate safety | 25% | **100%** | Conservative classifier, durable portal IDs, read-only candidates and explicitly confirmed *non-destructive* duplicate links; merged #574–#578 with CI. Does **not** claim automatic physical merging or real UI acceptance. |
| 1.4 | Source observation history | 20% | **100%** | PRs #580–#585 merged with green CI; real Windows 2026-10-16 backup/restore and isolated migration `0030→0033` PASS; live upgrade `0033` integrity OK, 51 applications and 133 human decisions preserved; 2 supervised LinkedIn runs produced 3 identities, 6 observations and 3 identities observed in multiple runs. Existing unverifiable history was not backfilled; four-portal operational acceptance remains Phase 2. |
| 1.5 | Portal visibility and Market Insights | 15% | **0%** | Operator can see all source URLs and duplicate links in review, with provenance-backed source breakdowns and no double-counted populations; backend/frontend tests, Playwright evidence, green CI and merge. |
| 1.6 | Integrated regression and evidence chain | 10% | **0%** | Four-source fixture pipeline; cross-site duplicate review, no loss of human decisions/applications, restart and guarded retention/backup rehearsal; source truthfulness tests, exact-head CI and merge. Existing individual test suites are not end-to-end acceptance. |

**Phase 1 total: 75%** (10 + 20 + 25 + 20). Remaining 25% is Phase 1.5 and 1.6.

## Phase 2 — Operational source integration

| ID | Subphase | Weight | Merged completion | Acceptance and evidence |
|---|---|---:|---:|---|
| 2.1 | LinkedIn capture continuity | 25% | **0%** | Exact-head regression and real Windows supervised capture evidence after Phase 1 changes; verify bounded traversal, source/detail quality and preserved prior human state; acceptance report, CI and merged fixes if any. Historical acceptance exists but not for this expanded release. |
| 2.2 | Indeed operational execution | 25% | **0%** | Validated bounded live capture or explicitly recorded portal-blocking evidence; truthful degraded state, complete detail provenance, idempotency and safe restart; operator evidence, relevant CI and merge. |
| 2.3 | InfoJobs Discovery integration | 25% | **0%** | Resolve open #572 (currently backend CI red); bounded saved-search execution, verified detail promotion, error/reporting, source-history tests and live supervised Windows acceptance; green CI and approved merge. |
| 2.4 | Jobgether Discovery integration | 25% | **0%** | Bounded in-app execution with trustworthy full description; unverified observations stay unpromoted; verification/Spain eligibility not invented; real operator acceptance, CI and approved merge. |

**Phase 2 total: 0%.** Feature existence or source observations do not constitute operational acceptance.

## Phase 3 — Operator workflow and release certification

| ID | Subphase | Weight | Merged completion | Acceptance and evidence |
|---|---|---:|---:|---|
| 3.1 | Multi-source human review and applications | 30% | **0%** | Real Windows capture → frozen AI work package → validated import → human decision → application lifecycle on multi-source evidence; demonstrate no overwritten decisions, exact-head CI and merged required fixes. |
| 3.2 | Multi-source analytics integrity | 30% | **0%** | Real market samples show population, date, portals and duplicate-adjusted counts; assert no unverified offer, salary or Spain eligibility is promoted; automated/UI tests plus operator evidence, CI and merge. |
| 3.3 | Migration, retention, restart and recovery | 25% | **0%** | On isolated copy: pre-migration verified backup, forward migration, post-restart data preservation, cleanup of unprotected records, preservation of linked/owned state, restore verification; exact-head CI and documented approval. |
| 3.4 | Final Windows operator sign-off | 15% | **0%** | A dated end-to-end acceptance report for the approved four-source scope with current checkout/runtime identities, unresolved blockers, CI and explicit user release acceptance; no unverified 100% operability statement. |

**Phase 3 total: 0%.**

## Execution order and evidence ledger

1. **Completed:** context/roadmap PR #579 merged into `main` with 11/11 green checks. Continue maintaining `jolt.md` on `main` after meaningful changes.
2. **Next:** #572 backend CI corrected and all 11 checks green; review its bounded supervised-import scope (not the full Discovery execution) and merge autonomously if still qualified.
3. **Then:** finish Phase 1.4 occurrence-level provenance ledger branch CI and PR; continue 1.5 Review Inbox/Market Insights source visibility and 1.6 integrated regressions.
4. **Afterward:** Phase 2 live source acceptance, then Phase 3 workflow and release certification; no implied approval for live outreach, data deletion, production-data modification or other high-risk irreversible actions; ordinary green PR merges are authorized.
5. For each accepted subphase, record **PR URL, merge commit SHA, exact-head check results, test evidence, real Windows evidence if required**, and date. Keep historical detail in PRs/tests/acceptance reports, not an ever-growing `jolt.md`.

## EA reporting contract

For every phase and every subphase, print:
`Phase 1.1 → Name → Brief description and verified status → 100% complete → Weight: 10% of phase total.`
Then `Total phase progress: 55%` (using that phase's current verified evidence), and repeat for subsequent phases.
Use only 0% or 100% completion per subphase; differentiate implementation/testing/CI status in the description. Recalculate from GitHub before every report.
