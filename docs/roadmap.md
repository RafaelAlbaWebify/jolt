# JOLT Roadmap v0.1

## Phase 0 — Foundation

- Product specification.
- Canonical domain and lifecycle.
- Source-adapter contract.
- Automation and testing strategy.
- Technology decision records.
- Repository structure and CI scaffold.

Exit criteria:

- Product boundaries are explicit.
- Domain states do not overlap.
- First vertical slice and automatic proof are defined.

## Phase 1 — Canonical local pipeline

- Manual/synthetic source intake.
- Immutable source evidence.
- Posting normalization.
- Identity resolution.
- Versioned profile.
- Explainable evaluation.
- Human review decision.
- SQLite persistence.
- Analysis-pack export.

Exit criteria:

- Complete intake-to-export workflow passes automatically.
- Data survives restart.
- Duplicate state, recommendation, review, and application stage remain separate.

## Phase 2 — Application workflow

- Pursue action creates an application.
- Preparation tasks and notes.
- Application timeline events.
- Follow-up dates.
- Interview stages.
- Outcomes.

Exit criteria:

- An application can be tracked from preparation to a clearly attributed final outcome.

## Phase 3 — LinkedIn fixture adapter

- Sanitized listing and detail fixtures.
- Adapter state machine.
- Listing identity extraction.
- Stale-detail detection.
- Listing-to-detail contract tests.
- Selective detail-enrichment policy.

Exit criteria:

- LinkedIn fixture workflow produces canonical opportunities reliably without live access.

## Phase 4 — Supervised LinkedIn capture

- Persistent local browser profile.
- User-controlled authentication.
- Bounded search execution.
- Listing scan.
- Selective detail enrichment.
- Diagnostics, screenshots, traces, and redacted report.

Exit criteria:

- One configured search can populate the review queue without one-off scripts or manual copying.

## Phase 5 — Market and career intelligence

- Structured posting requirements.
- Mandatory/preferred distinction.
- Duplicate-adjusted market populations.
- Source and role-family analysis.
- Outcome-aware rule analysis.
- Career-expansion evidence.

Exit criteria:

- Every insight states its population, sample size, and supporting evidence.

## Phase 6 — Additional source adapters

Priority candidates:

1. Indeed.
2. InfoJobs.

Each adapter must satisfy the existing canonical contract and fixture-based tests before live testing.

## Phase 7 — Packaging and replacement

- Reproducible Windows setup/package.
- Backup and recovery workflow.
- Portfolio-safe documentation and synthetic demo.
- Confirm feature parity needed from the legacy project.
- Archive/delete the legacy repository only after explicit acceptance.
- Rename or reposition the new repository if required.
