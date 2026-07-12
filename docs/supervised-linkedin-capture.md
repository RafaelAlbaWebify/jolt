# Supervised LinkedIn capture

JOLT uses a supervised local browser workflow for authenticated LinkedIn capture. It does not request, store, or transmit LinkedIn credentials.

## Manual boundary

The user performs only the actions that cannot safely be automated:

1. Start JOLT locally.
2. Run `tools\run-linkedin-capture.ps1`.
3. Log in to LinkedIn manually in the opened browser when necessary.
4. Apply or confirm the desired LinkedIn search filters.
5. Return to PowerShell and press Enter once.

The browser profile is persistent and remains under `.jolt/browser-profile`. It is excluded from Git and must never be uploaded.

## Automated work

After confirmation, the runner:

1. Reads a bounded number of currently visible job cards.
2. Extracts each durable LinkedIn job ID and listing metadata.
3. Opens each selected card.
4. Waits for the detail panel to expose the expected job identity.
5. Rejects stale or mismatched detail panels.
6. Captures screenshots and a Playwright trace.
7. Sends verified evidence to the local JOLT API for canonical ingestion.
8. Produces a single timestamped ZIP directly in Downloads.
9. Deletes its temporary staging directory.

The default limit is 10 jobs and the hard maximum is 50 jobs per invocation. The runner does not paginate, auto-apply, send messages, bypass login challenges, or solve CAPTCHAs.

## Command

From the repository root:

```powershell
.\tools\run-linkedin-capture.ps1 -SearchUrl "https://www.linkedin.com/jobs/search/?keywords=IT%20Support" -MaxJobs 10
```

The backend must be available at `http://127.0.0.1:8000` unless `-ApiUrl` is provided.

## Output

The ZIP is named like:

```text
JOLT_LINKEDIN_CAPTURE_20260713_001500.zip
```

It contains:

- `capture_summary.json`
- `api_result.json`
- `run.log`
- redacted HTML evidence
- visible-page screenshots
- `playwright_trace.zip`

Screenshots and traces can still contain information visible in the browser. Treat the ZIP as private evidence and review it before sharing.

## Failure behavior

If the local API is unavailable, browser evidence is still packaged and `api_result.json` records the connection failure. If a detail panel does not reach the expected job identity, that job is retained in the summary as unverified and is not submitted for canonical ingestion.
