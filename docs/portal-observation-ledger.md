# Phase 1.4A — Verified portal occurrence ledger

Status: implemented on a development branch; CI and merge are independent gates. This is a partial delivery toward Phase 1.4, **not** 100% completion of the subphase.

## Contract

- LinkedIn and Indeed live capture append one durable receipt per verified `CaptureItem` after a provenance artifact has been hashed.
- InfoJobs and Jobgether append an equivalent receipt only after an operator explicitly promotes a structurally validated observation; unverified staging does not create a receipt.
- Receipts retain portal, stable portal job ID, source URL, captured Posting/SourceDocument IDs, capture run/item IDs, artifact SHA-256 and observation timestamp.
- Unique `(portal, capture_item_id)` ensures replay of an identical item is idempotent. A changed digest for the same occurrence is rejected.
- The ledger deliberately has no foreign keys to temporary CaptureItems, SourceDocuments or Postings, so guarded retention can delete disposable records without deleting the provenance receipt. A receipt is **not** a copy of the full raw source description, proof of current job availability or permission to work from Spain.
- Existing `PostingSourceIdentity.first_seen_at/last_seen_at` remains the per-portal summary; the occurrence ledger adds event granularity.

## Evidence and remaining acceptance

- Test repeat verified LinkedIn capture, immutable digest, distinct run/item IDs and rejection of unverified captures; existing LinkedIn/Indeed/InfoJobs/Jobgether regression suites must remain green.
- Alembic forward migration `20261016_0033` and migration/recovery CI must pass without loss of owned applications or historical captured evidence.
- **Still needed for full Phase 1.4 acceptance:** an operator-accessible per-source history, migrations against a copy of the real legacy database, explicit policy for historical backfill and long-term immutable raw evidence, and real Windows multi-source acceptance.
- No live login, outreach, job application, destructive cleanup or mutation of the operator's local SQLite database is performed by this PR.
