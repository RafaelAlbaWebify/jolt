# Production migration and recovery policy

Date: 2026-09-20

## Policy

JOLT uses **forward-only Alembic migrations plus verified backup/restore recovery** for production operation.

Production recovery does **not** rely on arbitrary in-place Alembic downgrades of the active database.

Before any startup that detects the active database schema is behind the repository Alembic head, JOLT must:

1. stop any recorded JOLT services;
2. verify the supported runtime;
3. synchronize backend dependencies;
4. create a verified SQLite backup of the active database;
5. store that backup under `.jolt/backups/pre-migration/`;
6. only then run `alembic upgrade head`.

If the migration fails, startup fails closed and does not launch the backend or frontend.

## Recovery after migration failure

1. Do not repeatedly retry startup against a database whose migration failed.
2. Stop JOLT.
3. Identify the newest verified `JOLT_PRE_MIGRATION_<from>_TO_<to>_<timestamp>.zip`.
4. Verify it:
   ```powershell
   cd backend
   uv run python -m jolt.backup verify --backup <backup.zip>
   ```
5. Restore it to a **separate path** first:
   ```powershell
   .\JOLT.ps1 -Action restore -BackupPath <backup.zip> -RestoreTarget <isolated.db>
   ```
6. Confirm the restored database passes integrity/hash/schema checks.
7. Preserve the failed database for diagnosis before replacing it.
8. Replace the active database only while JOLT is stopped.
9. Restart only after the repository/runtime issue that caused the failed migration has been corrected.

## Why no automatic downgrade

Alembic downgrade support is not considered a production recovery guarantee for JOLT. SQLite schema/data transformations may not be safely reversible in every future migration. A verified pre-upgrade snapshot gives a stronger recovery boundary because it restores the exact pre-migration database bytes and schema revision.

Downgrade commands may be used on disposable test databases when validating migrations, but are not the supported active-database rollback mechanism.

## Backup guarantees

JOLT's backup format records:
- SHA-256 of the SQLite snapshot;
- byte size;
- Alembic revision;
- format version.

Verification checks the manifest, hash, size, SQLite `PRAGMA integrity_check`, and recorded schema revision.

Restore refuses to overwrite an existing target and re-verifies the restored hash.

## Certification requirement

Production migration/recovery is considered proven only when an automated disposable rehearsal demonstrates:

`previous revision → seed data → verified backup → upgrade head → seed survives → restore backup → restored revision/data match pre-upgrade state`

The rehearsal must run on the exact pull-request/release commit.
