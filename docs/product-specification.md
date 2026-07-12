# JOLT Product Specification v0.1

## Product purpose

JOLT is a local-first workbench that helps the user discover, evaluate, prioritize, pursue, and learn from job opportunities.

## Objectives

### Primary objective

Help the user obtain a suitable job faster and with better decisions.

### Secondary objective

Use verified market and application-outcome evidence to identify realistic career-expansion paths, skill priorities, and positioning improvements.

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
5. Evaluate the posting against a versioned user profile.
6. Rank it for human review.
7. Record the human decision.
8. Track preparation, application, follow-up, interviews, and final outcome.
9. Aggregate trustworthy market and outcome evidence.
10. Export an analysis pack for external review and feed approved changes back into profiles or product development.

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

- Ranked review queue.
- Explainable evaluation with evidence.
- Human review decision.
- Application work queue.
- Application timeline and outcome.
- Market and career-development insights.
- ZIP analysis pack containing JSON, CSV, and Markdown.

## Success measures

The product should eventually measure:

- Relevant unseen opportunities discovered.
- Time from discovery to review decision.
- Jobs reviewed per hour.
- False rejects and rule overrides.
- Applications submitted.
- Interviews obtained.
- Stage reached per application.
- Sources producing useful opportunities.
- Skills or constraints repeatedly blocking viable roles.

Captured-job count alone is not a success measure.

## Non-goals

- Automatic job applications.
- Recruiter messaging.
- Credential storage.
- CAPTCHA, authentication, paywall, or rate-limit bypass.
- Unattended mass crawling.
- Multi-user SaaS operation in the first product phase.
- Treating a machine recommendation as the final decision.

## Safety and privacy boundaries

- Local-first storage.
- Explicit user-controlled capture.
- Bounded pages, detail captures, delays, and timeouts.
- Dry-run and fixture modes for normal automated testing.
- No real credentials in source control or CI.
- External writes require explicit approval.
- Raw job text is excluded from public artifacts by default.

## First useful vertical slice

```text
Manual intake or saved LinkedIn fixture
→ preserve source evidence
→ normalize posting
→ resolve duplicates
→ evaluate against a versioned profile
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
→ evaluation queue
```

The live LinkedIn slice begins only after the source-neutral pipeline is working and covered by fixture-based tests.
