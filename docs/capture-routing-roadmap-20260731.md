# JOLT unified capture routing roadmap

Date: 2026-07-31
Status: implementation contract

## Problem statement

JOLT's user workflow says capture comes first, but the visible app currently exposes Review Inbox first and manual job entry can look like the primary intake path. That is wrong.

The working capture controls were previously hidden during Professional/Sources cleanup because the old Professional capture path was not cleanly connected to the normal opportunity pipeline. The product mistake was hiding the working capture entry instead of fixing the routing inconsistency.

Manual job entry must remain a fallback only. The main workflow must be capture-led.

## Current verified architecture

### Normal opportunity pipeline

This is the canonical job workflow:

```text
CaptureRun / CaptureItem
→ SourceDocument
→ Posting
→ Evaluation
→ Review Inbox
→ Application Pipeline
→ Market Insights
```

Observed backend behavior:

- `/api/captures/linkedin/live` creates a normal `CaptureRun`.
- It creates `CaptureItem` records.
- Verified job evidence is ingested through `ingest_capture_item`.
- Ingestion creates `SourceDocument` and `Posting` records.
- Those postings can then be evaluated and shown in Review Inbox / Market Insights.

This path is the target for job-opportunity capture.

### LinkedIn Command Center pipeline

This is the canonical LinkedIn presence workflow:

```text
LinkedIn page/profile/activity/network evidence
→ linkedin_presence_captures
→ LinkedIn recommendations/actions
→ LinkedIn Command Center
→ Market Insights positioning feedback
```

This path should be used for profile, activity, skills, recommendations, job tracker summary, network-quality observations, and content/activity evidence. It must not send messages, connect, comment, react, mass-crawl, or export contacts.

### Old Professional capture pipeline

This path exists separately:

```text
ProfessionalSourceOverride
→ ProfessionalCaptureRun
→ ProfessionalCaptureArtifact
→ local rendered-text/screenshot/metadata artifacts
→ Professional evidence review / structured extraction
```

This path is useful as a visible capture shell and evidence ledger, but it is not enough by itself because captured data can stay outside the canonical opportunity workflow unless routed.

## Product target

JOLT should have one obvious capture workspace and multiple explicit routing destinations.

The user should be able to answer immediately after a capture:

```text
What did JOLT capture?
Where did each item go?
What needs review?
What failed?
What should I do next?
```

## Target navigation

Recommended visible order:

```text
1. Capture & Evidence
2. Review Inbox
3. Application Pipeline
4. LinkedIn Command Center
5. Market Insights
6. Settings / Sources
```

Manual job add remains inside Review Inbox as a fallback, not the main action.

## Target capture routing model

Every captured page/item should produce a routing decision.

```text
captured item/page/artifact
→ classify deterministically
→ route to one of:
   - opportunity_candidate
   - linkedin_presence
   - market_signal
   - unclassified_evidence
   - rejected_noise
```

### Routing rules, deterministic first

#### opportunity_candidate

Route here when evidence is clearly a job offer, job detail, or job result item.

Signals:

- LinkedIn job detail URL or job ID.
- Text includes job title + company + location + description/responsibilities/requirements.
- Source is jobs search / jobs tracker / saved jobs / applied jobs.

Destination:

```text
CaptureRun / CaptureItem
→ SourceDocument
→ Posting
→ Evaluation
→ Review Inbox
```

#### linkedin_presence

Route here when evidence describes Rafael's LinkedIn profile or professional presence.

Signals:

- Profile URL, About, Experience, Skills, Certifications, Recommendations.
- Activity/posts.
- Job tracker summaries when not enough full job detail exists.
- Network/contact quality observations.

Destination:

```text
LinkedInPresenceCapture
→ LinkedIn Command Center
```

#### market_signal

Route here when evidence is aggregated job-market or search-result context, but not a specific ingestible job.

Signals:

- Search result pages with counts/filters but no verified detail payload.
- Repeated titles/skills/geographies extracted from listings.
- Recruiter-market observations.

Destination, initial version:

```text
Market Insights export/preparation pack only
```

Later version can add a first-class `market_signals` table if needed.

#### unclassified_evidence

Route here when useful evidence exists but JOLT cannot safely decide.

Destination:

```text
Captured Evidence Inbox
```

User can classify manually:

```text
Send to Review Inbox
Send to LinkedIn Command Center
Keep as market signal
Archive / ignore
```

#### rejected_noise

Route here for cookie banners, authwalls, empty pages, duplicate noise, or unrelated content.

Destination:

```text
Capture summary only, not active workflow
```

## Required UX

### Capture & Evidence page

Must show above the fold:

```text
Capture jobs / LinkedIn evidence
[Start capture]
[Capture settings]
[Browser/session status]
[Last capture summary]
```

The page must show:

```text
- capture targets/sources
- item limit
- timeout / scroll limits
- login/auth status when applicable
- capture run status
- routing summary
- link to Review Inbox when jobs were created
- link to LinkedIn Command Center when presence evidence was created
- unclassified evidence count
```

### Capture result summary

After each capture:

```text
Captured 42 items/pages

Routed:
- 28 job opportunities → Review Inbox
- 6 LinkedIn presence snapshots → LinkedIn Command Center
- 4 market signals → Market Insights package
- 3 unclassified → Evidence Inbox
- 1 rejected noise

Next:
[Go to Review Inbox]
[Review unclassified evidence]
[Refresh Market Insights]
```

### Review Inbox

Should contain only job opportunities waiting for a decision.

Top actions:

```text
Refresh list
Recalculate scores
Add job manually (fallback)
```

It should not be the main capture starting point.

### LinkedIn Command Center

Should continue to own:

```text
- profile/activity/network evidence
- recommendations
- profile/content/network actions
- LinkedIn export/import loop
```

### Market Insights

Should consume:

```text
- active retained postings/evaluations
- job preferences
- LinkedIn recommendations/signals
- imported market-preparation analysis
```

It should not own capture controls.

## Implementation roadmap

### PR A — Capture workflow audit and routing tests

Purpose: make the expected data flow explicit before UI changes.

Deliverables:

- This document.
- Backend tests proving normal LinkedIn live capture creates postings visible to opportunity index.
- Backend tests proving LinkedIn presence capture remains in LinkedIn Command Center and does not pollute Review Inbox.
- Frontend/Workbench test proving capture is the first visible workflow step.

Acceptance:

```text
A developer can read one document and know which capture path feeds which screen.
Tests fail if capture is hidden again or if job capture stops feeding Review Inbox.
```

### PR B — Restore visible Capture & Evidence workspace without pretending routing is solved

Purpose: restore the main visible capture entry safely.

Deliverables:

- Capture & Evidence first in sidebar.
- Start capture visible above source registry.
- Capture history visible.
- Read-only safety boundary visible.
- Manual add job remains fallback.
- Copy clearly says which captured evidence currently enters Review Inbox and which evidence is presence-only.

Acceptance:

```text
Open JOLT → Capture & Evidence appears first.
Start capture is visible without scrolling.
User can see where captured data is expected to go.
```

### PR C — Add capture routing summary

Purpose: make capture results understandable.

Deliverables:

- Backend response or derived UI model for routing counts.
- Capture result summary component.
- Counts for:
  - job_opportunities
  - linkedin_presence
  - market_signals
  - unclassified
  - rejected_noise
- Links to Review Inbox / LinkedIn Command Center / Evidence Inbox.

Acceptance:

```text
After a capture, JOLT tells the user what happened and where to go next.
```

### PR D — Evidence Inbox for unclassified captured artifacts

Purpose: avoid losing useful evidence that cannot be routed safely.

Deliverables:

- Unclassified evidence list.
- Preview source URL/title/text snippet/screenshot path.
- Manual actions:
  - create manual job from evidence
  - send to LinkedIn Command Center
  - keep as market signal
  - archive

Acceptance:

```text
No captured evidence disappears silently.
```

### PR E — Unified job search capture UX

Purpose: support the first real full job-offer capture.

Deliverables:

- LinkedIn job search URL field.
- Configurable item limit.
- Uses normal opportunity pipeline.
- Capture summary immediately shows created Review Inbox items.
- Job preferences visible nearby.

Acceptance:

```text
Paste job search URL → capture controlled batch → verified jobs appear in Review Inbox → Market Insights updates after scoring.
```

### PR F — Market + LinkedIn analysis loop hardening

Purpose: make the export/import loop reliable after real capture.

Deliverables:

- Market + LinkedIn export pack includes routing summary.
- Prompt.md explains job preferences, captured offers, LinkedIn evidence, and expected return package.
- Import package creates grouped actions already supported by Market Insights.

Acceptance:

```text
Fresh job capture → Market + LinkedIn pack → ChatGPT return ZIP → imported actions show preparation/application/search/profile priorities.
```

## Non-goals

Do not add:

- automated LinkedIn applications
- automated messages
- automated connections
- background LinkedIn monitoring
- mass contact export
- hidden scraping
- physical deletion of shared opportunity records

## Validation checklist for future merges

Before merging any capture-related PR:

```powershell
uv --project backend run pytest
npm --prefix frontend test
npm --prefix frontend run build
```

Manual smoke:

```text
1. Open JOLT.
2. Confirm Capture & Evidence is visible first.
3. Run a small capture.
4. Confirm routing summary appears.
5. Confirm job opportunities appear in Review Inbox.
6. Confirm LinkedIn presence evidence appears in LinkedIn Command Center.
7. Confirm Market Insights updates after recalculation.
```

## Product rule

If a working capture path is architecturally inconsistent, fix the routing. Do not hide the primary workflow unless an equal or better replacement is already implemented and verified.
