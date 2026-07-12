# JOLT Canonical Domain and Lifecycle v0.1

## Design rule

Capture evidence, employer posting data, machine evaluation, human review, application workflow, outcome, and market analysis are separate concepts. They must not be collapsed into one record or one status field.

## Lifecycle

```text
CapturedOpportunity
    ↓
PostingCandidate
    ↓
IdentityResolution
    ↓
Posting
    ↓
Evaluation
    ↓
ReviewDecision
    ├── reject/defer → Outcome
    └── pursue → Application → ApplicationEvent(s) → Outcome

Posting requirements + evaluations + reviews + outcomes
    ↓
MarketEvidence
    ↓
Profile, career, and product feedback
```

## Entities

### SearchDefinition

Represents user intent, not a source-specific URL.

Core fields:

- id
- name
- keywords
- locations
- remote policy
- date range
- experience levels
- employment types
- excluded terms
- enabled sources
- capture limits
- created at / updated at

A source adapter translates this definition into source-specific navigation or query parameters.

### CaptureRun

Represents one bounded execution of one source adapter.

Core fields:

- id
- search definition id
- source
- started at / completed at
- mode: fixture, dry-run, supervised-live
- limits used
- status
- counts
- warnings and failures
- adapter version

### CapturedOpportunity

Preserves source evidence before interpretation.

Core fields:

- id
- capture run id
- source
- source job id
- source URL
- captured at
- raw text or raw structured evidence
- content hash
- capture notes
- intake status
- failure reason

Intake states:

- captured
- invalid
- parse_failed
- parsed
- duplicate_candidate
- accepted
- ignored

Raw source evidence is immutable.

### PostingCandidate

A provisional normalized result that may still require correction or identity resolution.

Core fields:

- captured opportunity id
- extracted title
- company
- location
- work mode
- employment type
- description
- salary text
- posting date or age
- application method
- field-level confidence and evidence

### IdentityResolution

Separates duplicate handling from suitability evaluation.

States:

- new
- probable_duplicate
- confirmed_duplicate
- existing_posting_update
- unresolved

Evidence may include:

- canonical source URL
- source job ID
- content hash
- title + company + location
- similarity requiring human confirmation

### Posting

Canonical employer opportunity.

Core fields:

- id
- primary source
- canonical source URL
- external/source job ID
- title
- company
- location text
- work mode
- employment type
- description
- salary data when available
- publication and expiry information
- first seen / last seen
- active status

Posting states:

- active
- expired
- removed
- unknown

A posting does not know whether it was reviewed, pursued, or duplicated.

### PostingFieldEvidence

Supports auditable normalization.

Core fields:

- posting or candidate id
- field name
- extracted value
- confidence
- source excerpt
- extractor version
- user confirmed

### PostingRequirement

Structured market evidence extracted from a posting.

Core fields:

- posting id
- type: skill, experience, education, certification, language, availability, location, work mode
- name
- importance: mandatory, preferred, unclear
- value
- confidence
- evidence excerpt

### ProfileVersion

Immutable version of the user evaluation configuration.

Core fields:

- profile id
- version
- created at
- hard constraints
- preferences
- strategic signals
- rule weights
- explanation

Changing a profile creates a new version. Past evaluations retain the profile version used.

### Evaluation

One machine evaluation of one posting against one profile version.

Core fields:

- id
- posting id
- profile version id
- engine version
- created at
- status
- recommendation
- confidence
- optional ranking score

Statuses:

- completed
- insufficient_evidence
- failed
- superseded

Recommendations:

- pursue
- consider
- reject

### EvaluationSignal

Auditable reason for an evaluation result.

Core fields:

- evaluation id
- rule id
- category
- effect
- severity
- explanation
- source evidence
- evidence confidence

### ReviewDecision

Human decision; authoritative over the machine recommendation.

Core fields:

- id
- posting id
- evaluation id
- reviewed at
- decision
- reason code
- notes
- evaluation overridden
- override reason

Decisions:

- pursue
- consider
- defer
- reject
- needs_more_information

### Application

Created only after a pursue decision.

Core fields:

- id
- posting id
- created at
- current stage
- application URL
- resume version
- cover-letter version
- recruiter contact
- applied at
- follow-up at
- closed at

Application states:

- preparing
- submitted
- acknowledged
- recruiter_screen
- interviewing
- offer
- rejected
- withdrawn
- no_response
- closed

Detailed interview stages belong in ApplicationEvent rather than continually expanding the state enum.

### ApplicationEvent

Append-only timeline event.

Core fields:

- id
- application id
- event type
- occurred at
- notes
- evidence or related artifact

### Outcome

Explains how an opportunity ended and who made the decision.

Outcome types:

- rejected_by_user
- deferred_by_user
- duplicate
- invalid_posting
- no_application
- no_response
- rejected_by_employer
- withdrawn_by_user
- offer_declined
- offer_accepted
- role_closed

Core fields:

- id
- posting id
- optional application id
- recorded at
- outcome type
- stage reached
- reason code
- explanation
- feedback received

Outcomes are retained even when the active work queue is cleaned.

### MarketEvidence

A reproducible analytical projection, not an unexplained manually stored score.

Core fields:

- period
- population definition
- metric
- value
- sample size
- source filters
- confidence
- generated at

Every aggregate must be traceable to underlying valid postings, requirements, evaluations, reviews, applications, and outcomes.

## Invariants

- Raw capture evidence is immutable.
- Duplicate status is not an evaluation recommendation.
- A human review decision is not an application stage.
- Employer rejection is distinct from user rejection.
- Past evaluations retain the profile and engine versions used.
- Missing or uncertain evidence cannot silently become a hard rejection.
- Market metrics state their population and sample size.
- Cleaning active queues never destroys outcome evidence.
