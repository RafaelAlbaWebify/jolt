# Reproducible release and deployment

JOLT's supported production deployment is a source release for a single-user Windows workstation.

## Release artifact

`tools/build-jolt-release.py` creates a deterministic ZIP from the exact tracked contents of a clean Git commit.

The archive contains:
- every Git-tracked repository file in stable path order;
- normalized ZIP timestamps and permissions;
- `RELEASE_MANIFEST.json` containing the exact Git commit, JOLT version, tracked-file count, file modes, sizes and SHA-256 hashes.

The same clean Git commit must produce a byte-identical archive. CI builds the archive twice and compares SHA-256 hashes.

## Build locally

From the repository root:

```powershell
python .\tools\build-jolt-release.py `
    --output .\artifacts\JOLT-release.zip `
    --manifest-output .\artifacts\JOLT-release-manifest.json
```

The build refuses a dirty worktree.

## Deploy

1. Extract the certified release ZIP to a local folder on a supported Windows x64 machine.
2. Install only the prerequisites in `docs/SUPPORTED_RUNTIME.md`.
3. Run `./tools/assert-jolt-runtime.ps1`.
4. If migrating an existing installation, preserve the existing `backend/data/jolt.db` and `.jolt/browser-profile` outside the extracted release until the new checkout is ready.
5. Run `./tools/start-jolt.ps1`.
6. Startup creates a verified pre-migration backup automatically when the existing database schema is behind the release Alembic head.
7. Verify backend health, runtime identity and frontend reachability.

## Release certification

A production release candidate is acceptable only when the exact commit that produced the release ZIP has green:
- CI;
- Playwright acceptance;
- full-cycle Playwright certification;
- production clean-install certification;
- migration recovery certification;
- reproducible release certification;
- no unresolved P0/P1 release blocker;
- valid dated real-site LinkedIn failure/recovery evidence for the current capture behavior.

Production readiness is a property of the exact release commit, not of a nearby branch or historical run.
