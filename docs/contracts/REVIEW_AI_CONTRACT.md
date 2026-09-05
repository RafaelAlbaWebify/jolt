# Review / AI Module Contract

## Responsibility
Expose pending opportunities for review, export trustworthy job/candidate evidence to ChatGPT, validate returned reasoning, and preserve user-owned review state.

## Inputs
Posting/source evidence, current job-search preferences, candidate evidence, deterministic hardline evidence, AI work-package update.

## Outputs
Pending Review Inbox, validated AI review metadata, separate human ReviewDecision state, strategy/context updates that do not overwrite protected state.

## Guarantees
- process order: source evidence -> Stage 1 hardlines -> candidate evidence -> Stage 2 fit -> recommendation;
- strict sequential per-job review for bulk packages;
- REJECT/MANUAL_REVIEW stops fit;
- deterministic hardline contradictions are rejected on import;
- pursue/strong_pursue require resolved eligible geography and clear language/clearance;
- duplicates cannot be positive;
- every imported posting ID/source ID must belong to the intended capture;
- source evidence and human decisions remain authoritative.

## Dependencies
Capture/evidence records, hardline parsers, candidate evidence, unified AI exchange/import contracts.

## Failure behavior
Malformed, contradictory or ownership-invalid AI payloads fail validation/import rather than being silently normalized into a positive decision.

## Constraints
Missing evidence is uncertainty. Study/lab/project/certification evidence must not be promoted to unsupported professional depth.

## Non-responsibilities
Source acquisition, application lifecycle ownership, auto-apply, autonomous career authority.