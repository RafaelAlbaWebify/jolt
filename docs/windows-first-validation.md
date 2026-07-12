# First Windows and authenticated LinkedIn validation

This is the first project phase that requires the user's Windows environment. CI proves the code, fixture browser workflow, migrations, frontend build, and PowerShell syntax. It cannot prove the authenticated LinkedIn DOM or local Windows process behavior.

## Before the first run

Clone or update the repository, then open PowerShell in the repository root.

Required commands must be available in `PATH`:

```powershell
git --version
node --version
npm --version
uv --version
```

Do not share LinkedIn credentials, browser-profile contents, screenshots, traces, or validation packages publicly.

## Controlled application start

```powershell
.\tools\start-jolt.ps1
```

Expected result:

- Dependencies synchronize successfully.
- Alembic upgrades the local database.
- Backend health responds at `http://127.0.0.1:8000/api/health`.
- Frontend responds at `http://127.0.0.1:5173`.
- The browser opens JOLT.
- `.jolt/services.json` records the two service process IDs.
- `.jolt/logs` contains separate standard-output and error logs.

## Authenticated LinkedIn smoke test

Use a small bounded test first:

```powershell
.\tools\start-jolt.ps1 `
    -StartLinkedInCapture `
    -SearchUrl "https://www.linkedin.com/jobs/search/?keywords=IT%20Support" `
    -MaxJobs 3
```

The user manually logs in or confirms the existing session, confirms the search filters, and presses Enter once. JOLT then captures at most three visible cards.

Validate in the interface:

1. A capture run appears under **LinkedIn capture history**.
2. Accepted and rejected counts are visible.
3. **Inspect capture** shows listing identities and verification reasons.
4. Verified items create or reuse canonical opportunities.
5. Rejected items are not ingested as opportunities.

## Diagnostic package

After the test:

```powershell
.\tools\validate-jolt.ps1
```

A single `JOLT_WINDOWS_VALIDATION_<timestamp>.zip` is created directly in Downloads. Upload that ZIP for review only after checking that its local logs contain no information you do not want to share.

The LinkedIn capture command separately creates `JOLT_LINKEDIN_CAPTURE_<timestamp>.zip`. Screenshots and Playwright traces may contain private browser-visible information.

## Stop JOLT

```powershell
.\tools\stop-jolt.ps1
```

The stop command uses the recorded process IDs and removes the runtime state file. It does not delete the database, logs, browser profile, or captured evidence.
