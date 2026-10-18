# Batch 44 — Verification, schema and archiving tools

Four complete source files reviewed on 2026-10-18. Source-level only, without running database or browser operations.

| File | Risk / observed safeguard |
|---|---|
| `tools/audit-remote-source-verification.py` | SQLite opened read-only; filters LinkedIn-origin AI reviews for absent/conflicted authoritative geography verification. Reports source text and URLs by default, meaning stdout and written revalidation packs are sensitive. `--max-jobs` lower-bounded and forced IDs may exceed that bound by design. |
| `tools/jolt-schema-fk-audit.py` | **Medium:** `sqlite3.connect(str(db_path))` can open for writing and is not strict read-only; some read queries join interpolated table names taken from SQLite schema (trusted schema identifiers, but quotations are not escaped). Outputs detailed foreign key reference samples that may include private IDs. |
| `tools/jolt-archive-imported-capture-batches.py` | Default is preview-only and `--apply` required for archiving. **Medium:** accepts database URL with no explicit confirmation of environment/backup before status-changing operation; ensure user understands archival is persistent. |
| `tools/test_ai_workflow.py` | Tests all context modes, module scope, freshness and session handoff, but uses `assert` statements, which Python `-O` disables. Generates files under `.ai/generated` and does not isolate changes. |

Do not equate source inspection with actual database mutation/protection test. These are four distinct tools, no measured LOC savings. Branch-local count +4 from currently merged 215/300 gives 219/300 (73%), whereas other PRs may cover separate files. Reconcile by unique filename after merging.
