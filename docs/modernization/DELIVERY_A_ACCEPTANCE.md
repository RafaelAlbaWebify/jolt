# Delivery A — Frozen acceptance and integration plan (2026-10-28)

## Objective
Close foundational safety and observability before starting task-specific exports in Delivery B. Measure complete capabilities, not number of PRs. Preserve human decisions, applications, raw capture evidence and existing contracts.

## Already integrated, not to repeat
- #667 SQLite read-only baseline and strategy.
- #668 latest verified capture selection in one ranked query.
- #669 all-group preflight for unified review packages.
- #670 SQLite atomic review-bundle groups.
- #671 Market observation source-capture coverage diagnostic.
- #672 Professional Evidence freshness independence.
- #673 truthful Review Inbox export scope.
- #674 same-content AI feedback replay protection.
- #675 SQLite page/index/free-page baseline.
- #676 redacted operator diagnostic ZIP: **pending merge and explicit CI certification** at freeze time.

## Remaining A implementation scope, as one coherent follow-up capability PR
1. **Import safety** — enumerate every importer/sidecar write path and protected state; use isolated test fixtures for exact replay, conflicting replay, partial SQLite failure, JSON sidecar failure, restart/retry and reconciliation. No assumption of distributed transactions. Backwards compatibility for existing package contracts.
2. **Processing accounting** — use canonical capture IDs, source hashes and per-module output version/feedback where available. Report explicit pending/complete/failed/not-applicable/unknown, never classify other modules as completed from Market observation alone. Avoid large per-item SQL loops and duplicate historical ledger tables without need.
3. **Operator acceptance/report** — extend #676's one-command redacted report with processing counters, missing observations, phase timings and manifest source SHA. No secrets, raw vacancy text or application/private messages. Refuse unsafe deletion; live API/browser validation, if added, must be opt-in and labelled.
4. **Performance and recovery** — compare frozen fixture timing/query count and verify rollback, restore and protected-record invariants. Preserve evidence and version the baseline manifest.

## Acceptance evidence register (fill from real execution)
| Criterion | Minimum evidence | Status |
|---|---|---|
| Full import replay/failure matrix | Named deterministic tests and outputs | NOT VERIFIED |
| Recoverable cross-store partial writes | Documented recovery and tests | NOT VERIFIED |
| Per-module coverage/unknowns | Consistent fixtures + report | NOT VERIFIED |
| Redacted single-command report | Automated fixture + one operator ZIP | PARTIAL (#676 pending) |
| Before/after query/time/storage | Frozen fixture measurements | NOT VERIFIED |
| Exact-head CI + merge | Green checks on final head | NOT VERIFIED |
| One Windows read-only acceptance | Operator diagnostic ZIP inspected | NOT VERIFIED |

## Execution/communication contract
Keep the implementation in one branch with cohesive commits; do not ask for approval between files/tests. CI failures must be repaired in the same PR. Continue independent work while GitHub runs, without assuming checks are complete. One operator command/upload at final acceptance; never reset/migrate/purge the real Windows database without explicit consent. Any unrelated UI polish, broader export restructuring or retention changes go to B/C backlog, not A.
