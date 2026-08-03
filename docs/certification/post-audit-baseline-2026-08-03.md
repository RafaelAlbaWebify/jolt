# JOLT post-audit recovery baseline — 2026-08-03

## Scope

This record captures the exact state immediately after completion of audit issue #131 and verifies the highest-value recovery controls against the real local database.

## Repository baseline

- Audited `main` commit: `45aa2c684703f802157e1bc84c0d94266701a344`
- Audit issue: #131, closed completed
- Application workflow fixes merged through PR #238
- Database Alembic revision: `20260730_0018`

## Local quality evidence

Executed on Windows against the clean post-audit checkout:

- Ruff check: passed
- Ruff formatting check: passed
- Pyright: 0 errors, 0 warnings
- Backend tests: 260 passed
- Backend line coverage reported by the suite: 74%
- Frontend dependency audit during service preparation: 0 vulnerabilities

The combined visual/review certification did not complete because it exposed the two real-data blockers documented below. The quality gate itself passed before those runtime audit failures.

## Verified database and recovery evidence

The active database was inspected read-only and reported:

- SQLite `PRAGMA integrity_check`: `ok`
- capture runs: 17
- capture items: 274
- postings: 231
- applications: 29
- application events: 180
- outcomes: 2

A permanent post-audit backup was created with the existing supported backup command:

- format: `jolt-sqlite-backup-v1`
- database size: 12,263,424 bytes
- SHA-256: `f1c779ff65568d857b53d32bc3f56d2bc290236b1293fcfd8dae31328ef30f5c`
- source path included in manifest: false
- backup verification: passed

The backup was restored to an isolated temporary database. The restored database:

- passed `PRAGMA integrity_check`;
- retained Alembic revision `20260730_0018`;
- matched the backup SHA-256 exactly;
- retained the same key table counts;
- did not overwrite or modify the active JOLT database.

This proves the current backup and isolated-restore path works against the real post-audit database.

## Runtime certification blockers discovered

### #239 — archived capture count inconsistency

Archived capture `47a4b8d2-fc54-458c-be51-b1bbe31e14c2` contains three persisted verified items and three page-visible unique IDs, but its stored `observed_item_count` is zero.

The items remain present and the database is structurally healthy, so this is a confirmed historical metadata inconsistency rather than demonstrated data loss. No ad hoc mutation was made to the active database.

### #240 — unbounded review-audit opportunity load

Measured endpoint behavior on the real database:

| Endpoint | Time | Items | Response size |
| --- | ---: | ---: | ---: |
| `/api/health` | 0.044 s | — | 58 bytes |
| `/api/opportunity-index?include_reviewed=true` | 0.129 s | 51 | 53,849 bytes |
| `/api/application-index` | 0.167 s | 206 | 219,453 bytes |
| `/api/opportunities` | 37.605 s | 231 | 1,690,565 bytes |

The review audit still calls the full `/api/opportunities` collection with a fixed 15-second timeout. This no longer scales to the real accumulated dataset and also starves the visual journey while the backend is occupied.

## Baseline conclusion

The conservative recovery objective is complete:

- exact audited release commit identified;
- clean local quality gate passed;
- real database integrity verified;
- supported backup successfully created and verified;
- isolated restore successfully completed and matched by hash and row counts;
- active database remained untouched;
- certification blockers were isolated as #239 and #240 rather than hidden or repaired speculatively.

The full visual/review certification remains intentionally incomplete until #239 and #240 are resolved. This baseline must not be described as a fully passing Windows certification package.