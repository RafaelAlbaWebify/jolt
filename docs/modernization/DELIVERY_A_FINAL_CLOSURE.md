# Delivery A — Final two-PR closure plan (2026-10-28)

## PR 1: source-grounded discrepancy investigation (this change)

The October 28 read-only operator diagnostic found 33 expected verified market identities without observations and 272 observations outside the verified-linked set. Those are **counts of distinct (capture run, source job) pairs**, not proof of corruption or eligible vacancies.

Extend the operator report with aggregate-only classification:
- Missing market observations, grouped by capture source and run status.
- Unexpected observations grouped by **no capture item / unverified capture / missing posting link / missing source document**, capture source and run status.
- No job IDs, search URLs, captured text, personal data, database writes or automatic backfill.

**Acceptance:** frozen SQLite fixtures prove classification, counts, redaction and read-only behavior. CI must be green on final head. After merge, the operator runs one updated ZIP and returns it; explain actual group counts rather than inventing root causes.

## PR 2: recovery and release verification

Implement a documented, tested operator-controlled reconciliation procedure for interrupted unified multi-store imports. Fail closed on unverified state. A recovery step must inspect SQLite and relevant JSON sidecars; do not blindly clear journal state or replay any incomplete import. Cover fault injection and idempotency, protect human review/applications, and certify restore on disposable fixtures.

Where possible run baseline and targeted UI/API health checks with one read-only Windows acceptance script; capture actual timings and relevant versions. If a feature cannot be established from evidence, mark it an explicit follow-up, not a passed A gate.

Do not expand A with separate UI polishing or speculative refactors. B owns full per-module analysis/export redesign.
