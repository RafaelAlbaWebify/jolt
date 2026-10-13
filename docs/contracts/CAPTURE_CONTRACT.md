# Capture Module Contract

## Responsibility
Acquire bounded/manual or supervised job-source evidence, preserve provenance, and create capture/item/source/posting records suitable for downstream review.

## Inputs
- manual intake text/metadata;
- supervised LinkedIn search URL and bounded capture request;
- interactive browser state controlled by the user.

## Outputs
- CaptureRun/CaptureItem/CapturePage/CaptureArtifact records;
- SourceDocument evidence;
- normalized Posting identity links;
- capture diagnostics, warnings and stop reason.

## Guarantees
- source evidence is preserved separately from derived evaluation;
- capture provenance/IDs remain auditable;
- login/checkpoint/CAPTCHA conditions fail closed rather than bypassing controls;
- archive/cleanup cannot erase higher-level human review/application state.

## Dependencies
SQLite/SQLAlchemy/Alembic, visible Chromium/Playwright for LinkedIn, posting identity/dedup services.

## Failure behavior
Partial/failed runs must expose status/warnings/stop reason. A partial capture must not be presented as complete coverage.

## Non-responsibilities
Final career decisions, AI fit reasoning, auto-application, recruiter messaging, unattended mass crawling, credential storage.
## InfoJobs supervised evidence boundary (October 2026)

The InfoJobs browser adapter initially offers a bounded **read-only observation** of at most five offer links from a user-visible Chrome search. It reads a detail page only after validating the InfoJobs host and rejects redirected/mismatched identity paths. A captured title, body text and SHA-256 digest are observational artifacts, **not** verified employer content or authorization to work from Spain. No CaptureRun/Posting, AIReview, human decision or Application may be created from this experimental path until live extraction fidelity and canonical identity are accepted and its existing persistence transaction is integrated and tested.

Acceptance is gated on a real operator Chrome run with positive listing-link discovery, correct title/description per offer, reliable identity, and explicit handling of failed/partial pages. Unit/CI fixtures alone are not sufficient.
