# Windows certification workflow

Run the complete local proof from any PowerShell working directory:

```powershell
& "C:\path\to\jolt\JOLT.ps1" -Action certify
```

The command requires a clean Git checkout and uses the repository discovered by `JOLT.ps1`; no `cd` is required.

It performs these steps:

1. starts JOLT cleanly and runs the complete read-only review and capture evidence audit;
2. creates and verifies a consistent SQLite backup through the online backup API;
3. restores that backup to a temporary isolated database;
4. verifies the restored SHA-256 hash against the backup manifest;
5. records the Git branch, commit, schema revision, hashes, and privacy boundaries;
6. stops JOLT and deletes the temporary backup and restored database;
7. writes one ASCII-safe ZIP to Downloads.

Output:

```text
C:\Users\<user>\Downloads\JOLT_CERTIFICATION_YYYYMMDD_HHMMSS.zip
```

The certification ZIP contains:

- `certification-summary.json`;
- `README.txt`;
- the nested `JOLT_REVIEW_AUDIT_*.zip` produced during the same run.

It does not contain the active database, temporary backup database, restored test database, raw capture payloads, or absolute user paths.

The command refuses to run when the repository has uncommitted changes. It never overwrites the active database and never promotes the restored test database into production.
