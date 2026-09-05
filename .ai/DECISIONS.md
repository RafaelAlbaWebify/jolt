# JOLT Decision Ledger

This file records accepted durable decisions. `PROJECT_MEMORY.md` remains a deeper historical source; conflicts must be resolved by current code/test evidence and then reflected here.

## D-001 — Clean rebuild, not legacy continuation
- Date: 2026-07
- Decision: current `RafaelAlbaWebify/jolt` is the implementation repository; legacy `jolt-job-tracker` is reference-only.
- Reason: avoid carrying forward untrusted architecture/state.
- Consequence: do not patch or base new work on the archived legacy repo.
- Status: active.

## D-002 — Local-first, single-user product
- Decision: JOLT runs locally first and stores its operational data locally.
- Reason: privacy, operator control, lower complexity and current user need.
- Alternatives: hosted multi-user SaaS.
- Consequence: auth/tenancy/cloud deployment are not current prerequisites.
- Status: active.

## D-003 — Evidence/provenance separated from judgment
- Decision: JOLT captures, validates, persists and presents evidence; human state is authoritative; ChatGPT may provide judgment-heavy reasoning.
- Reason: auditability and avoiding opaque local heuristics becoming career authority.
- Consequence: source evidence and human decisions cannot be overwritten by AI-derived context.
- Status: active.

## D-004 — Durable ownership hierarchy
- Decision: Application state > human review > posting identity > evidence lineage > capture lifecycle > UI state.
- Reason: capture cleanup previously caused application visibility regressions.
- Consequence: archive/cleanup operations must preserve higher-level state and receive cross-workflow regression tests.
- Status: active.

## D-005 — Prefer archive/hide to physical deletion
- Decision: user-facing capture cleanup should archive/hide central records rather than infer a safe deletion graph.
- Reason: real SQLite FK failures and complex shared dependencies.
- Consequence: destructive deletion requires explicit maintenance semantics and full dependency proof.
- Status: active.

## D-006 — Supervised browser capture only
- Decision: LinkedIn automation uses visible/supervised Chromium, bounded capture and fail-closed login/checkpoint behavior.
- Reason: safety, reliability and product boundary.
- Consequence: no stored credentials, CAPTCHA bypass or unattended mass crawling.
- Status: active.

## D-007 — Unified ChatGPT exchange layer
- Date: 2026-09
- Decision: one unified AI work package carries relevant current context/evidence across major JOLT sections; ChatGPT returns validated structured feedback.
- Reason: reduce fragmented prompts/files and make reasoning updates auditable.
- Consequence: market/profile/application/skills/data-quality exchanges share common ownership/contract rules.
- Status: active.

## D-008 — Strict sequential job review
- Date: 2026-09-04
- Decision: bulk job review must process each vacancy independently in capture order, complete Stage 1 before Stage 2, and aggregate only after every posting has a result.
- Reason: earlier 100-job bulk digestion missed hardline blockers that were obvious in single-job review.
- Consequence: `strict_sequential_per_job`, self-audit and exact-result coverage are permanent review protocol requirements.
- Status: active.

## D-009 — Hardline precedence and positive eligibility gate
- Date: 2026-09-04
- Decision: deterministic/source-supported hardline blockers override technical fit; pursue/strong_pursue require resolved geography plus clear language/clearance; duplicates cannot be positive.
- Reason: high technical similarity must not rescue ineligible jobs.
- Consequence: importer rejects contradictory AI returns.
- Status: active.

## D-010 — Missing evidence is uncertainty, not absence
- Decision: partial LinkedIn/candidate evidence cannot prove something does not exist.
- Reason: captures can be bounded/partial and historical authwall captures were misleading.
- Consequence: AI outputs must not turn missing profile/network observations into negative facts.
- Status: active.

## D-011 — Preserve credibility boundaries
- Decision: certification, lab, study, project or adjacent exposure is not professional production experience unless evidence says so.
- Reason: truthful job-fit analysis and application material.
- Consequence: AI and deterministic summaries must not inflate experience.
- Status: active.

## D-012 — Merge gates are product gates
- Decision: CI, Playwright acceptance and full-cycle Playwright certification must all be green for the exact PR head before merge.
- Reason: prior UI/functionality regressions escaped narrower tests.
- Consequence: do not weaken tests merely to merge.
- Status: active.

## D-013 — Search strategy should improve recall/precision without weakening hardlines
- Date: 2026-09-04
- Decision: broad Worldwide/Remote capture may remain useful for recall, but actionable recommendations require affirmative eligibility evidence; improve query/source targeting rather than relaxing eligibility rules.
- Reason: real 79-job capture produced many country-local false positives.
- Status: active.