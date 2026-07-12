# Source Adapter Contract v0.1

## Purpose

External job sites must remain replaceable adapters. LinkedIn is the first implementation, but the core application must not depend on LinkedIn page concepts.

## Adapter responsibilities

A source adapter may:

- Translate a SearchDefinition into source-specific navigation.
- Read bounded result pages.
- Extract listing candidates.
- Enrich selected candidates with detail evidence.
- Report diagnostics and failures.

A source adapter must not:

- Evaluate suitability.
- Create application records.
- Decide that a duplicate should be rejected.
- Store credentials.
- Bypass authentication or source protections.
- Contact employers or submit applications.

## Canonical outputs

### ListingCandidate

- source
- source job ID
- source URL
- title
- company
- location text
- work-mode text
- posting age/date text
- summary text
- salary text
- employment type text
- application method
- sponsored flag
- captured evidence
- captured at

### DetailCaptureResult

- listing candidate identity
- capture status
- full description
- additional structured fields
- raw evidence reference
- expected identity
- observed identity
- identity verified
- warnings
- failures
- captured at

### CaptureDiagnostics

- adapter name and version
- search URL or replay reference
- pages attempted
- listing cards found
- listing candidates accepted/rejected
- detail captures attempted/succeeded/failed
- duplicate source identities observed
- stale-detail detections
- selector fallbacks used
- timing information
- bounded limits
- warnings and errors

## LinkedIn first-adapter requirements

The LinkedIn adapter must model the page as a state machine rather than a sequence of fixed sleeps.

For each candidate:

1. Read a durable listing identity where available.
2. Record the listing-card evidence.
3. Select the card.
4. Wait for a meaningful detail-panel state change.
5. Verify that the detail panel belongs to the expected job ID or expected title/company identity.
6. Reject stale or mismatched detail content.
7. Capture the full description and additional evidence.
8. Record diagnostics before continuing.

The adapter must account for:

- split list/detail layout
- current job ID in URLs
- promoted or repeated cards
- previously applied labels
- external application versus Easy Apply
- pagination or scrolling
- stale detail panels
- jobs disappearing between listing and detail capture
- partial loading and retries

## Capture depths

### Listing scan

Fast, bounded extraction used for discovery, identity resolution, and preliminary filtering.

### Detail enrichment

More expensive capture performed only for candidates selected by explicit policy.

The core application determines which candidates require enrichment. The adapter performs the requested capture and reports evidence.

## Test modes

Every adapter must support or be testable through:

- sanitized fixture mode
- dry-run mode
- supervised live mode

CI relies on fixture mode. Live mode is local and user-controlled.

## Future adapters

Indeed and InfoJobs must implement the same canonical outputs even when their layouts differ. Optional source fields remain optional and must not force source-specific concepts into the core domain.
