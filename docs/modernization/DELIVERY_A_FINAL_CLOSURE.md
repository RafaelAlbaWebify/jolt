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


## PR 2 implementation / operational gate

The read-only operator report now inspects parseability of the unified journal, feedback sidecar and market preparation sidecar, without including raw values. A new `tools/accept-delivery-a.ps1` runs a single operator ZIP diagnostic, measures its elapsed time and checks that the database byte size is unchanged. A matching unit fixture verifies missing, corrupt and valid sidecar classifications without modifying data.

### Fail-closed interruption recovery runbook

1. Stop all JOLT writers before manual investigation; do not import again, truncate the journal, or purge any SQLite/JSON records.
2. Create independent backup copies of the SQLite database (using SQLite's backup API while writers are stopped) and **all** backend/data JSON sidecars, including the journal. Verify that the backups are readable.
3. Run the read-only diagnostic. If an import is incomplete, inspect the journal's last stage and compare the actual state of SQLite records and each sidecar against the imported package or a known-good backup. A reported `applied` checkpoint documents progress but does **not** prove every write committed; a reported `applying` checkpoint may have already written data.
4. If the result cannot be established unequivocally, leave the package blocked and restore only from a user-approved, verified consistent backup. Do not attempt selective replay against live data.
5. Perform any recovery and failure-injection rehearsal on **disposable copies** first, then verify integrity, protected human decisions, and sidecar readability. Live restoration requires explicit operator consent.

**Important gate:** this phase provides safe diagnosis and a manual recovery policy, not atomic distributed transactions or tested automatic repair. Windows API/browser operation and before/after performance are not verified by a read-only ZIP. Any remaining fail-closed recovery gaps must be declared instead of treating CI success alone as full operational certification.
