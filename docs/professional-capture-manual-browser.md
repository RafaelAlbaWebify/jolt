# Professional capture manual browser workflow

Professional Intelligence capture is intentionally supervised and user-driven.

## Workflow

1. Click **Open Chromium to prepare capture** in the single **Current capture session** panel.
2. JOLT opens a visible persistent Chromium profile at LinkedIn.
3. Sign in manually if LinkedIn asks for authentication.
4. Navigate manually to the exact LinkedIn page you want captured, such as a profile page or a job-search results page.
5. Return to JOLT.
6. Click **Capture current Chromium page** from the same **Current capture session** panel.
7. JOLT captures the already-open page as governed local evidence.

## Why this workflow exists

LinkedIn can show authwall, signup, cookie, premium, app-prompt, or other interstitial pages when a fresh browser is opened. JOLT should not guess the page or silently capture an authwall. The user prepares the browser and JOLT captures the exact page after explicit confirmation.

## Session model

- JOLT stores the local Chromium browser profile under `backend/data/professional-browser-profile`.
- JOLT does not ask for or store LinkedIn credentials.
- The browser remains user-controlled during preparation.
- The active action controls live in one top-level panel, not inside every history card.
- History cards are read-only for old runs except review, cancel, and delete actions.
- Only one **Capture current Chromium page** button should be available.
- If multiple prepared batches exist after reload, JOLT uses the newest prepared run for the single top-level capture action and lets old batches be deleted from history.

## Deletion model

A non-running capture batch can be deleted from history after typing `DELETE CAPTURE RUN` for that specific run. Deletion removes the database records and governed evidence folder for that run when present. The deletion phrase is tracked per run so deleting one stale batch does not corrupt or reuse another run's confirmation state.
