# Rejected / Abandoned Approaches

## RA-001 — Use legacy `jolt-job-tracker` as the implementation base
- Rejected because: current JOLT is a clean rebuild with different domain/ownership contracts.
- Evidence: README/project history.
- Reconsideration: no; legacy may be consulted only as historical reference.

## RA-002 — Physical deletion as normal capture cleanup
- Rejected because: live SQLite FK failures and hidden/shared dependencies made posting deletion unsafe; it also risked destroying higher-level workflow state.
- Evidence: `docs/jolt-architecture-audit-20260729.md` and later cleanup regressions.
- Reconsideration: only as explicit maintenance tooling after a complete dependency audit and dedicated destructive-operation tests.

## RA-003 — Treat Opportunities as a generic all-postings index
- Rejected because: user intent is a pending review inbox; mixing reviewed/applied/stale imports caused confusing lifecycle behavior.
- Evidence: architecture audit and pending-inbox behavior.
- Reconsideration: only through a separate explicit broader index/view, not by weakening Review Inbox semantics.

## RA-004 — Use local deterministic scoring as final career authority
- Rejected because: heuristics are suitable for validation/extraction but not nuanced final career judgment.
- Evidence: `PROJECT_MEMORY.md` ChatGPT reasoning-layer contract.
- Reconsideration: deterministic code may expand only for explicit, auditable invariants or extraction rules.

## RA-005 — Parallel/aggregate-first AI digestion of large job batches
- Rejected because: earlier bulk reviews produced attractive high-fit results while missing hardline geography/work-authorization constraints already present in source text.
- Evidence: Roy Jorgensen/Anaconda investigation and PR #378.
- Reconsideration: only if a new reasoning protocol is independently proven at least as reliable as strict per-job Stage-1 review.

## RA-006 — Interpret generic `Remote` as global eligibility
- Rejected because: many country-local remote jobs are not available to a Spain-based candidate.
- Evidence: real capture reviews and hardline-review-1.1 policy.
- Reconsideration: never without explicit employer hiring/contract evidence.

## RA-007 — Treat foreign location alone as automatically acceptable when no prohibition is written
- Rejected because: v5-style reasoning overcorrected and recommended US/local roles merely because no explicit work-right sentence was found.
- Evidence: historical AI review failures.
- Reconsideration: positive decisions require affirmative compatibility evidence.

## RA-008 — Weaken viewport/Playwright certification to pass a UI change
- Rejected because: certification exists to catch real supported-layout regressions.
- Evidence: 1680x945 Settings/Data overflow regression in `PROJECT_MEMORY.md`.
- Reconsideration: only if supported product viewport requirements themselves are deliberately changed.

## RA-009 — Assume a LinkedIn Connections partial capture represents the whole network
- Rejected because: virtualized/nested scrolling produced ~19 unique contacts while LinkedIn showed 500+ connections.
- Evidence: PR #377 problem statement.
- Reconsideration: only when capture quality explicitly says bounded complete and the requested limit/coverage semantics are clear.

## RA-010 — Use invalid LinkedIn login/authwall captures as profile evidence
- Rejected because: login/checkpoint pages are not candidate evidence and can distort profile conclusions.
- Evidence: PR #374 and current candidate-evidence export exclusions.
- Reconsideration: no; retain only for audit/quality diagnostics.

## RA-011 — Rely on chat history as project memory
- Rejected because: long chats degrade, reach context limits and force repeated reconstruction.
- Evidence: this migration.
- Reconsideration: no; repository + `.ai/` is authoritative, chats are temporary work sessions.