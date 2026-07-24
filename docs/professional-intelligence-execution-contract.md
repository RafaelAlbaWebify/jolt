# Professional Intelligence execution contract

This document defines the boundary that must exist before JOLT can perform any supervised LinkedIn capture.

## Execution state

Live capture is not available. Readiness remains blocked until all of the following exist:

- a supervised browser runner;
- an explicit browser-session boundary;
- a verified local evidence root;
- explicit per-run user confirmation;
- visible stop controls and failure recording.

## Browser-session boundary

- JOLT must not collect or export credentials, cookies, tokens, local storage, session storage, or Playwright storage-state files.
- Authentication, when required, must occur interactively in a user-visible browser.
- The user must remain present during capture.
- Each run must start from an explicit user action.
- No unattended or scheduled LinkedIn capture is permitted.

## Evidence types

Only these artifact types are permitted:

- `screenshot_png`
- `rendered_text_json`
- `capture_metadata_json`
- `page_diagnostics_json`

Artifacts must use a direct relative path under:

`professional-intelligence/<run-id>/<source-id>/<filename>`

Absolute paths, nested traversal, `..`, unsupported extensions, and sources outside the immutable run snapshot are invalid.

Every artifact must include a valid lowercase-normalized SHA-256 digest.

## Page completeness

Each planned source must finish with exactly one status:

- `complete`: expected page identity and visible content were captured;
- `partial`: the page loaded but one or more required evidence elements were missing;
- `failed`: navigation, authentication, page identity, or evidence capture failed.

A run cannot be considered complete while any planned source lacks a terminal completeness status.

## Text extraction

1. Visible rendered DOM text is the primary evidence source.
2. Hidden DOM content must not be collected.
3. OCR is allowed only when rendered DOM text is unavailable and screenshot evidence exists.
4. OCR output must be labelled as derived evidence.
5. Every text artifact must link to its screenshot and capture metadata.

## Privacy and retention

- Default retention is 30 days.
- Configured retention must be between 1 and 365 days.
- Credentials, cookies, tokens, browser storage state, private messages, and hidden DOM content are prohibited evidence.
- Deletion must remove both artifact files and metadata after retention expires.
- A future UI must allow the user to delete a run and its evidence immediately.

## Account-action prohibition

The runner must not connect, follow, like, comment, apply, send messages, accept invitations, dismiss notifications, or perform any other LinkedIn account mutation.

## Acceptance gate before live capture

A live implementation may begin only after automated tests prove:

- explicit start is required;
- only approved run-snapshot URLs are visited;
- all account-action controls are ignored;
- session material is never written to evidence;
- evidence paths and hashes validate;
- failures create terminal diagnostics;
- stop/cancel behavior is deterministic;
- the resulting evidence package can be reviewed before analysis.
