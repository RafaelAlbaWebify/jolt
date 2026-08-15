# JOLT Product Specification v0.1

## Product purpose

JOLT is a local-first workbench that captures, preserves, structures, and exposes job-search evidence across opportunity discovery, application tracking, outcomes, and market intelligence.

JOLT is not the authoritative career-decision layer. It may retain explainable evaluation metadata for provenance and comparison, but decisions such as whether to apply, reject an opportunity, rank career priorities, or choose development actions remain with the human user and, when desired, an external reasoning layer such as ChatGPT.

## Objectives

### Primary objective

Maintain a trustworthy evidence chain that helps the user review opportunities, track applications, and understand the market without losing source provenance.

### Secondary objective

Make verified market and application-outcome evidence easy to export and interpret externally, while preserving a clear separation between stored evidence and career judgment.

## Initial user and environment

- Single user.
- Runs locally on Windows during the initial product phase.
- GitHub is used for source control, review, CI, and backup.
- External job sources are treated as adapters, not as the core domain.

## Core workflow

1. Discover opportunities through supervised automated capture or manual intake.
2. Preserve the original source evidence.
3. Normalize the opportunity into a canonical posting.
4. Resolve identity and duplicates.
5. Retain versioned, explainable evaluation metadata where available.
6. Present evidence for human review without making the final career decision.
7. Record the human decision.
8. Track preparation, application, follow-up, interviews, and final outcome.
9. Aggregate trustworthy market and outcome evidence with explicit provenance and populations.
10. Export an analysis pack for external interpretation and feed only explicitly approved changes back into profiles or product development.

## Input paths

### First release

- Manual text or HTML intake.
- Saved synthetic or sanitized LinkedIn fixtures.
- Supervised LinkedIn capture after the canonical pipeline is proven.

### Later adapters

- Indeed.
- InfoJobs.
- Other sources only through the same source-adapter contract.

## Primary outputs

- Evidence-backed opportunity review queue.
- Explainable evaluation metadata and provenance where retained.
- Human review decision.
- Application work queue.
- Application timeline and outcome.
- Market evidence with source, population, deduplication, and freshness context.
- ZIP analysis pack containing JSON, CSV, and Markdown for external review.

## Success measures

The product should eventually measure:

- Verified unseen opportunities captured.
- Time from discovery to human review decision.
- Jobs reviewed per hour.
- Evidence completeness and provenance coverage.
- Applications submitted.
- Interviews obtained.
- Stage reached per application.
- Sources producing useful opportunities.
- Market requirements observed repeatedly across canonical vacancies.

Captured-job count alone is not a success measure.

## Non-goals

- Automatic job applications.
- Recruiter messaging.
- Credential storage.
- CAPTCHA, authentication, paywall, or rate-limit bypass.
- Unattended mass crawling.
- Multi-user SaaS operation in the first product phase.
- Treating a machine recommendation as the final decision.
- Authoritatively deciding Apply/Reject, career priorities, skill priorities, or outreach strategy.

## Safety and privacy boundaries

- Local-first storage.
- Explicit user-controlled capture.
- Bounded pages, detail captures, delays, and timeouts.
- Dry-run and fixture modes for normal automated testing.
- No real credentials in source control or CI.
- External writes require explicit approval.
- Raw job text is excluded from public artifacts by default.
- Stored evidence and external interpretation remain separate concerns.

## First useful vertical slice

```text
Manual intake or saved LinkedIn fixture
→ preserve source evidence
→ normalize posting
→ resolve duplicates
→ retain versioned evaluation metadata
→ present evidence for human review
→ record human review decision
→ persist locally
→ export an analysis pack
→ prove the workflow automatically
```

## First automated-source slice

```text
One configured LinkedIn search
→ supervised listing capture
→ canonical listing candidates
→ duplicate filtering
→ selective detail enrichment
→ evidence review queue
```

The live LinkedIn slice begins only after the source-neutral pipeline is working and covered by fixture-based tests.
