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

## InfoJobs supervised staging — 2026-10-13

Operator-observed evidence may be staged only from an intact bounded InfoJobs JSON batch (1–5 offers). Source identity derives from the 32-hex `/of-i...` URL suffix, not a free-form slug. Validate the SHA-256 of each complete captured page and isolate the `Descripción` section through `Categoría`; keep the raw page and isolated description in the existing CaptureArtifact. Reject malformed/duplicate/ambiguous evidence atomically. Default CLI runs roll back; explicit `--commit` stages new CaptureRun/CapturePage/CaptureItem/CaptureArtifact records and ignores known source identities. All remain `observed_unverified` with null Posting/SourceDocument references; no Review or Application changes. This is **not** proof of source fidelity, vacancy availability, work-from-Spain eligibility or complete downstream ingestion.

## October 13 source evidence completeness follow-up

InfoJobs and Jobgether share the existing CaptureRun/CaptureItem/CaptureArtifact persistence boundary and distinct supervised Chrome launchers. The launchers can now execute optional observation staging after a bounded capture; persistent writes require explicit `-StageObservations -CommitObservations`, otherwise no mutation is attempted. Jobgether's browser JSON retains its extracted job description, which previously was discarded; InfoJobs additionally parses the employer and location from the observed detail header. Existing observations are **not retroactively enriched** by these changes. Both sources remain `observed_unverified`: neither browser extraction nor a listed applicant country by itself satisfies source/remote-Spain eligibility gates or creates a Posting, Review, or Application. Production acceptance requires a fresh user-supervised run and review of actual captured details and corresponding stored artifacts.

## Explicit source evidence import for review (October 2026)

From existing Capture History, the operator may deliberately import a complete supervised InfoJobs or Jobgether observation into the existing SourceDocument / Posting workflow. The backend rechecks the stored CaptureArtifact SHA-256, canonical source identity, title and employer consistency, and full captured description before calling the existing `ingest_capture_item` transaction. It fails closed for historical Jobgether reports with missing descriptions, malformed/partial evidence, redirects or discrepancies, and is idempotent on repeat requests. This operation **does not establish work-from-Spain eligibility**, issue a positive ChatGPT AI review, make a human pursue decision, or create an Application. Human confirmation is required in Capture History; existing review hardlines remain authoritative.
