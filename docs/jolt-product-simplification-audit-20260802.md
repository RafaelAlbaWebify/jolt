# JOLT Product Simplification Audit — 2026-08-02

## Purpose

Audit the current product as it exists on `main`, not as earlier roadmap documents described it. Every visible workflow and supporting backend path is classified as keep, simplify, merge, move, complete, rename, remove, or investigate.

The guiding principle is practical operation:

1. Capture jobs.
2. Review opportunities.
3. Pursue selected opportunities.
4. Track applications and outcomes.
5. Learn from evidence.

LinkedIn profile/presence intelligence is a separate supporting workflow and must not look like a second job-discovery pipeline.

## Current top-level UI map

`frontend/src/Workbench.tsx` currently owns five primary views:

| Current view | Frontend root | Main responsibility today | Audit direction |
|---|---|---|---|
| Capture & Evidence | `ProfessionalIntelligence` | Primary job capture, secondary configured-source capture, source registry, evidence root, professional run ledger | Split by user goal |
| Review Inbox | `App` | Pending opportunities, scoring, evidence, review decisions, manual intake | Keep and simplify |
| Application Pipeline | `ApplicationDashboard` | Application board, tasks, interviews, contacts, documents, timeline, archive | Keep; reduce status/control complexity |
| LinkedIn Command Center | `LinkedInCommandCenter` | Separate LinkedIn target registry, Playwright capture, evidence snapshots, recommendations, ZIP import/export | Make authoritative for profile/presence |
| Market Insights | `MarketIntelligence` | Market metrics, preferences, LinkedIn comparison, preparation rules, ZIP import/export | Keep core analysis; remove redundant loops |

Global `DataTools` currently combines capture batch history, reviewed decision correction, and analysis export. This is not one coherent user task and should be split into focused history/data-management surfaces.

## Confirmed duplicate LinkedIn systems

### System A — Professional/configured-source capture

Frontend ownership:

- `ProfessionalIntelligence.tsx`
- `ProfessionalCaptureRuns.tsx`
- `ProfessionalSourceEditor.tsx`
- `ProfessionalEvidenceRoot.tsx`

Backend ownership:

- `/api/professional-intelligence/*`
- professional source registry and overrides
- professional capture plan and capture runs
- professional artifacts, evidence root, routing summary, review, extraction, opportunity import

Storage:

- `professional_source_overrides`
- `professional_capture_runs`
- `professional_capture_artifacts`
- `professional_evidence_settings`
- local professional evidence root
- persistent professional capture browser profile

Current problems:

- Combines profile, career/job, network and discovery sources.
- Selects sources indirectly through priority plus `max_sources`, not explicit user choice.
- Can import career-page text into Review Inbox despite the canonical URL-driven job collector already doing this more reliably.
- Uses implementation-led controls: scroll batches, item bounds, source count, stop-on-failure.
- Uses a separate evidence ledger from normal job captures.
- Can report `completed with gaps` even when no usable source is produced.

### System B — LinkedIn Command Center

Frontend ownership:

- `LinkedInCommandCenter.tsx`

Backend ownership:

- `/api/linkedin-command-center`
- `/api/linkedin-command-center/captures`
- `/api/linkedin-command-center/captures/playwright`
- `/api/linkedin-command-center/captures/playwright-batch`
- recommendation import/status/export endpoints

Storage:

- `linkedin_presence_captures`
- `linkedin_presence_recommendations`
- capture targets stored separately in browser `localStorage`
- separate screenshot/output location and persistent browser behavior

Current problems:

- Duplicates profile, activity, skills, certification and job-search targets already represented in the Professional registry.
- Uses a frontend-local registry rather than the persisted backend registry.
- Includes job-search targets even though its stated responsibility is professional presence.
- Contains ZIP parsing/import logic in the frontend.
- Mixes evidence acquisition, action tracking, outreach, lead research and cleanup.

## Primary architecture decision

There must be one authoritative LinkedIn profile/presence workflow.

### Keep as canonical job-discovery path

`LinkedInJobCaptureLauncher` and the canonical pipeline:

`capture_runs -> capture_items -> source_documents -> postings -> evaluations -> Review Inbox -> Applications -> Market Insights`

This path is already proven with bounded, multi-page LinkedIn job search capture and verified job-detail ingestion.

### Make LinkedIn Profile the canonical presence path

Consolidate profile, experience, featured, certifications, skills, recommendations and activity capture under one user-facing workspace currently represented by LinkedIn Command Center.

The final workspace should own:

- one persisted source registry;
- explicit source selection or practical presets;
- profile/presence evidence capture;
- evidence freshness and latest status;
- deterministic extraction;
- target-role comparison;
- recommended profile actions;
- evidence links and recommendation status.

It must not own Review Inbox job import.

### Remove or narrow Professional capture

The Professional capture system should either:

1. become the backend evidence engine behind the LinkedIn Profile workspace, with the duplicate Command Center capture implementation removed; or
2. be retired after required evidence/recommendation data is migrated.

The preferred direction is to reuse the more mature Professional artifact integrity/run model as an internal engine while removing its separate user-facing workflow and career/job importer.

## Section audit

### 1. Capture Jobs

#### Keep

- Exact LinkedIn search URL input.
- Maximum jobs and pages bounds.
- Visible user-present Chromium.
- Canonical verified job-detail pipeline.
- Manual job intake as fallback.
- Capture batch history, archive and diagnostics.

#### Simplify

- Rename top-level workspace from `Capture & Evidence` to `Capture Jobs`.
- Show practical defaults and hide advanced bounds unless expanded.
- Separate active job capture history from profile/presence capture history.
- Summarize terminal outcomes first: usable jobs, duplicates, failed items, rejected noise.
- Keep dense evidence/routing diagnostics behind an expansion.

#### Move

- Configured profile/activity capture to LinkedIn Profile.
- Source registry and evidence-root controls to LinkedIn Profile settings or global Settings.

#### Remove from normal job workflow

- `Profile, activity, and configured-source capture` panel.
- `Maximum sources` implicit selection.
- Professional career-source import button.
- Profile/network routing summaries in job capture history.

### 2. Review Inbox

#### Keep

- Pending-only review queue.
- Search and score sorting.
- Opportunity inspector.
- Evidence, strengths, gaps, blockers and uncertainties.
- Separate Refresh and Recalculate Scores actions.
- Manual intake fallback.

#### Simplify

- Review decisions should map to distinct next actions.
- Proposed minimal set:
  - Pursue
  - Reject
  - Need information
  - Defer only if it has a real resurfacing mechanism/date
- Investigate whether `consider` is distinct from `need information` or `defer`.
- Blocked/do-not-pursue jobs should default to a collapsed blocked view rather than compete with actionable review work.

#### Move

- Reviewed-decision correction from global Data Tools into a Review History view.

### 3. Application Pipeline

#### Keep

- Preparing, Applied, Interviewing, Offer and Closed lanes.
- Next action and due date.
- Tasks, interviews, contacts, documents and timeline.
- Outcome recording.
- Archive as a visibility state.

#### Simplify

- Preserve detailed backend statuses but present fewer board-level stages.
- Do not allow arbitrary drag transitions that misrepresent real application events.
- Make the primary action on every card the actual next action.
- Hide empty advanced tabs until an application exists.

#### Investigate

- A `pursue` decision currently creates a board candidate before an application record exists. Determine whether this preparation state is useful or whether `Pursue` should create the preparation record immediately.
- Verify whether contacts and documents are used enough to justify permanent top-level tabs versus contextual sections.

### 4. LinkedIn Profile

#### Keep

- User-approved read-only capture.
- Profile/presence evidence snapshots.
- Change tracking.
- Deterministic explicit-signal extraction.
- Recommendations with status.
- Profile, experience, skills, certification and activity coverage.

#### Consolidate

- Replace two source registries with one persisted registry.
- Replace two capture launchers/browser profiles with one implementation.
- Replace separate screenshot/evidence locations with one contained evidence root.
- Route all profile evidence here.

#### Remove or relocate

- Job Tracker and jobs-recommendation pages from the profile registry unless they provide a distinct, clearly labelled LinkedIn-algorithm signal. They must never import jobs into Review Inbox.
- Outreach and lead-research boards unless there is a proven current workflow using them.
- Browser-local target persistence.

#### Rename

`LinkedIn Command Center` -> `LinkedIn Profile` or `LinkedIn Presence`.

### 5. Market Insights

#### Keep

- Actionable fit distribution.
- Technical fit as a secondary diagnostic only.
- Target/outside-target split.
- Role families, work modes, companies, locations and skills.
- Blockers, actionable gaps and study priorities.
- Timeframe/source filters.
- Active job-search preference summary.

#### Move

- Full job-search preference editor to Settings; show a summary and link from Market Insights.

#### Simplify

- Show target scope by default.
- Keep `all roles` as a secondary diagnostic.
- Keep only metrics that change search strategy, preparation or application decisions.
- Convert static hard-coded preparation rules into a small explanation layer or remove them when they merely repeat top gaps.

#### Investigate/remove

- `JOLT_MARKET_LINKEDIN_PREPARATION.zip` export.
- Market preparation ZIP/JSON import.
- Browser-side ZIP decompression in `MarketIntelligence.tsx`.
- LinkedIn recommendation import/export loop if direct in-app analysis and the normal ChatGPT workflow already provide the same outcome.

## Global Data Tools audit

Current `DataTools` combines:

- analysis-pack export;
- reviewed-decision correction;
- capture batch history.

These belong to different user goals.

Target direction:

- Review History inside Review Inbox.
- Job capture history inside Capture Jobs.
- Profile capture history inside LinkedIn Profile.
- Export, archive and retention under Settings & Data.

## Navigation target

1. Capture Jobs
2. Review Inbox
3. Applications
4. LinkedIn Profile
5. Market Insights

Secondary:

- Settings & Data
- Developer diagnostics collapsed and non-primary

## Open PR hygiene

Known stale open PRs from superseded stacked/experimental directions must be closed after verifying no unique unmerged behavior remains:

- #187 experimental manual prepared capture
- #190–#198 old stacked UX chain
- #205 old capture restoration branch

Do not merge or rebase these branches into current `main`.

## First simplification implementation sequence

### PR 1 — Product boundary and navigation

- Rename Capture & Evidence to Capture Jobs.
- Remove configured-source capture controls from Capture Jobs.
- Keep professional capture history hidden from the job workflow.
- Rename LinkedIn Command Center to LinkedIn Profile.
- Add clear cross-links: Capture Jobs for vacancies; LinkedIn Profile for profile evidence.
- No backend deletion yet.

### PR 2 — One source registry and explicit selection

- Choose the persisted Professional registry as the authoritative source registry.
- Expose it inside LinkedIn Profile.
- Add explicit source selection and presets.
- Remove browser-local Command Center target registry.
- Exclude job-import behavior.

### PR 3 — One profile capture engine

- Route LinkedIn Profile capture through one browser/evidence implementation.
- Preserve integrity review and deterministic extraction.
- Remove duplicate capture endpoints only after frontend migration and data checks.

### PR 4 — Review and application simplification

- Rationalize decision states.
- Move reviewed history out of Data Tools.
- Make application next-action flow primary.

### PR 5 — Market and data-tool simplification

- Move preferences to Settings.
- Remove redundant ZIP import/export loops after confirming no unique outcome.
- Split capture histories by domain.

## Non-goals

- No broad rewrite.
- No generalized provider framework.
- No speculative AI-agent layer.
- No physical database deletion without dependency and retention checks.
- No compatibility adapters for workflows selected for removal.
