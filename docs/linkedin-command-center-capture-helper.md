# LinkedIn Command Center capture helper

This helper supports user-present LinkedIn evidence capture for JOLT.

It is intentionally not a scraper or automation bot:

- it opens a visible Chromium window;
- the user logs in and navigates manually;
- the user explicitly presses Enter before capture;
- it captures only the currently approved page state;
- it does not click, scroll through lists, send messages, export contacts, or run background monitoring.

## Example

Start JOLT, then run:

```powershell
cd C:\Users\ralba\Documents\GitHub\jolt
uv --project backend run python .\tools\jolt-linkedin-user-present-capture.py `
  --url "https://www.linkedin.com/in/YOUR-PROFILE/" `
  --category profile `
  --title "Profile baseline"
```

The browser opens. Navigate manually if needed. When the exact LinkedIn section is visible and approved, return to the terminal and press Enter.

The helper stores:

- visible page text in JOLT as a LinkedIn Command Center evidence snapshot;
- final URL;
- timestamp and change tracking through the existing JOLT API;
- a screenshot under `Downloads\JOLT_LINKEDIN_CAPTURES`.

## Useful categories

- `profile`
- `public_profile`
- `analytics`
- `activity`
- `network_contact`
- `network_request`
- `target_company`
- `target_recruiter`
- `job_search`
- `other`

Use one capture per meaningful page/section. Keep captures curated rather than broad.
