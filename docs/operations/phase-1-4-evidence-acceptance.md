# Phase 1.4 — Historical evidence and retention acceptance

## Safe legacy provenance policy

- **No automatic migration/backfill of historical receipts**: existing data is never rewritten merely because a new observation table exists. The receipt table is additive.
- Backfill uses only already-verified, promoted `CaptureItem` records with a matching `PostingSourceIdentity`, readable artifact, and correct SHA-256. Unverified, deleted, mismatched, or metadata-only captures are never promoted.
- `backfill_portal_observation_receipts(session)` defaults to a savepoint-backed dry run. An explicit `commit=True` is required for durable writes; this is not exposed as an automatic startup task.
- Old occurrence timestamps use the persisted capture run's `started_at`, not the date of backfill. The original item and artifact must still exist. If retention already deleted them, historical detail **cannot** be reconstructed from summary records or hashes.
- Receipts preserve identifiers, URL, digest and time, **not immutable raw description bytes**. A missing raw artifact remains missing after cleanup. Never imply that retaining a SHA-256 makes the original source recoverable.
- Receipt records intentionally do not hold foreign keys to disposable capture items or archived postings. Their original IDs remain historical, not guaranteed dereferenceable. Do not use a historical receipt by itself to assert current vacancy, location eligibility or human judgment.

## Verification and boundary

Disposable SQLite regression cases cover dry-run rollback, explicit commit, idempotent re-execution, post-restart source-history response, tamper rejection, and receipt survival after transient artifact/capture-item deletion. CI checks backend Ruff/format/Pyright/pytest, migrations, Windows scripts, clean install and full cycle.

This is **not yet** a real Windows acceptance against the operator's existing historical database. Before claiming Phase 1.4 fully accepted, verify migration/backup against an isolated operator database snapshot, read historical receipt counts, inspect a real repeated verified capture and observe no changes to active applications or review decisions. No production-data change or portal login is needed for this code PR.
