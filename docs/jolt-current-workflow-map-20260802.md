# JOLT Current Workflow Map — 2026-08-02

This map records the current `main` product relationships before simplification.

## 1. Capture Jobs

### UI

- `Workbench` view id: `professional`
- `ProfessionalIntelligence`
- `LinkedInJobCaptureLauncher`
- `ProfessionalCaptureRuns`
- `ProfessionalSourceEditor`
- `ProfessionalEvidenceRoot`

### Job discovery path

`LinkedInJobCaptureLauncher`

→ local LinkedIn collector

→ `POST /api/captures/linkedin/live`

→ `live_capture_workflow.run_linkedin_live_capture`

→ `capture_runs` / `capture_items`

→ `source_documents` / `postings`

→ current evaluation

→ `/api/opportunity-index`

→ Review Inbox

→ `/api/market-intelligence`

This is the canonical and proven opportunity path.

### Configured-source path

`ProfessionalIntelligence`

→ `GET/POST /api/professional-intelligence/sources*`

→ professional source registry and overrides

→ create/authorize/start Professional capture run

→ `professional_capture_runs` / `professional_capture_artifacts`

→ evidence review / deterministic extraction / routing summary

→ optional career-source opportunity import

→ canonical opportunity pipeline

This is a parallel evidence system and the main consolidation target.

## 2. Review Inbox

### UI

- `App`
- opportunity index list
- opportunity inspector
- automated review/readiness/evidence components
- manual intake

### Main path

`GET /api/opportunity-index`

→ `opportunity_index.list_opportunity_index`

→ pending unreviewed opportunities

Inspector:

`GET /api/opportunity-detail/{posting_id}`

→ `opportunity_workbench.get_opportunity_workbench`

Decision:

`POST /api/opportunities/{posting_id}/reviews`

→ `workflow.record_review`

Manual fallback:

`POST /api/intake/manual`

→ `workflow.ingest_manual`

A `pursue` review makes the posting visible to Application Pipeline even before an application record exists.

## 3. Applications

### UI

- `ApplicationDashboard`
- `ApplicationWorkflow`
- `ApplicationTasks`
- `ApplicationInterviews`
- `ApplicationContacts`
- `ApplicationDocuments`
- timeline

### Main path

`GET /api/application-index`

→ pursued postings and application records

Create preparation/application record:

`POST /api/opportunities/{posting_id}/applications`

Transitions:

`POST /api/applications/{application_id}/transitions`

Outcomes:

`POST /api/applications/{application_id}/outcomes`

Archive/restore:

`POST /api/applications/{application_id}/archive`

`POST /api/applications/{application_id}/restore`

Work items use a separate application work-items router.

## 4. LinkedIn Command Center

### UI

- `LinkedInCommandCenter`
- capture target registry stored in browser `localStorage`
- individual/batch Playwright capture
- manual capture
- recommendation creation and status boards
- ZIP/JSON recommendation import
- export package

### Main path

Dashboard:

`GET /api/linkedin-command-center`

Manual evidence:

`POST /api/linkedin-command-center/captures`

Playwright evidence:

`POST /api/linkedin-command-center/captures/playwright`

`POST /api/linkedin-command-center/captures/playwright-batch`

Recommendations:

`POST /api/linkedin-command-center/recommendations`

`POST /api/linkedin-command-center/recommendations/import`

`POST /api/linkedin-command-center/recommendations/{id}/status`

Export:

`GET /api/linkedin-command-center/export`

Storage:

- `linkedin_presence_captures`
- `linkedin_presence_recommendations`

This overlaps materially with the configured-source Professional system.

## 5. Market Insights

### UI

- `MarketIntelligence`
- target/all scopes
- timeframe/source filters
- editable job-search preferences
- LinkedIn comparison
- hard-coded preparation rules
- market preparation export/import

### Main path

Metrics:

`GET /api/market-intelligence`

→ `market_intelligence.build_market_intelligence`

Preferences:

`GET/POST /api/job-search-preferences`

LinkedIn data:

`GET /api/linkedin-command-center`

Preparation export:

`GET /api/market-intelligence/preparation-pack`

Preparation import:

`GET/POST /api/market-intelligence/preparation-import`

Storage includes file-backed preferences and file-backed imported market preparation packages in addition to database market evidence.

## 6. Global Data Tools

### UI

- `DataTools`
- `ReviewedDecisions`
- `CaptureHistory`

### Responsibilities currently combined

- complete analysis pack export;
- reviewed-decision correction;
- normal capture-batch history and archive.

This should be separated by user goal:

- Review History in Review Inbox;
- job capture history in Capture Jobs;
- profile capture history in LinkedIn Profile;
- export/archive/retention in Settings & Data.

## 7. Storage families

### Canonical job/application family

- `capture_runs`
- `capture_items`
- `source_documents`
- `postings`
- `evaluations`
- `review_decisions`
- `applications`
- `application_events`
- outcomes/readiness/work-item tables

### Professional configured-source family

- `professional_source_overrides`
- `professional_capture_runs`
- `professional_capture_artifacts`
- `professional_evidence_settings`
- local evidence root

### LinkedIn Command Center family

- `linkedin_presence_captures`
- `linkedin_presence_recommendations`
- browser-local capture target registry
- separate capture screenshots/output

### File-backed analysis/configuration

- job-search preferences
- market preparation imports
- other export/import package state

## Primary consolidation targets

1. One job capture path: canonical URL-driven job collector.
2. One LinkedIn profile source registry.
3. One LinkedIn profile capture engine and evidence store.
4. No career/job import from profile capture.
5. One location for job-search preferences.
6. Remove analysis ZIP loops that do not create unique value.
7. Split global Data Tools by user task.
