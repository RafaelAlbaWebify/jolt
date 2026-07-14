# JOLT backup and restore

JOLT stores local application data in `backend/data/jolt.db` by default.

## Create a verified backup

Run the repository-independent launcher from any directory:

```powershell
& "C:\path\to\jolt\JOLT.ps1" -Action backup
```

The default output is an ASCII-safe ZIP in the current user's Downloads folder:

```text
JOLT_BACKUP_YYYYMMDD_HHMMSS.zip
```

A custom output path can be supplied:

```powershell
& "C:\path\to\jolt\JOLT.ps1" -Action backup -BackupPath "D:\Backups\JOLT_BACKUP.zip"
```

The archive contains only:

- `jolt.db`, created through SQLite's online backup API;
- `manifest.json`, containing the backup format, creation time, size, SHA-256 hash, and Alembic revision.

The source filesystem path is not written into the manifest. The archive is verified immediately after creation.

## Restore safely

Restore always requires an explicit new target path:

```powershell
& "C:\path\to\jolt\JOLT.ps1" `
  -Action restore `
  -BackupPath "C:\Users\ralba\Downloads\JOLT_BACKUP_20260714_120000.zip" `
  -RestoreTarget "C:\Users\ralba\Downloads\JOLT_RESTORE_TEST\jolt.db"
```

The restore workflow:

1. verifies the ZIP structure and backup format;
2. verifies the database SHA-256 hash and byte size;
3. runs SQLite `PRAGMA integrity_check`;
4. verifies the Alembic revision against the manifest;
5. restores to a new target only;
6. verifies the restored database again.

It refuses to overwrite the active JOLT database or any existing target. Replacing the active database remains a deliberate manual operation after the restored copy has been inspected and validated.
