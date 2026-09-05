# JOLT File Map

This is a compact navigation map, not a file inventory.

## Bootstrap / project memory
- `.ai/` — canonical AI project-control package. Future chats start here.
- `PROJECT_MEMORY.md` — durable historical product boundaries, ownership hierarchy, merge rules and regressions.
- `README.md` — user/developer startup, product purpose and high-level capability.
- `docs/` — deeper architecture, product, testing, backup and historical design documents.

## Backend
- `backend/src/jolt/main.py` — FastAPI app composition and top-level routes.
- `backend/src/jolt/database.py` — SQLAlchemy models/session and persistence authority.
- `backend/migrations/` — Alembic schema history.
- `backend/src/jolt/capture_*`, `live_capture_workflow.py`, `linkedin_*` — capture/evidence pipelines.
- `backend/src/jolt/opportunity_*`, `workflow.py`, `review_*` — Review Inbox/opportunity lifecycle.
- `backend/src/jolt/application_*` — durable Applications, work items, readiness, archival/cleanup/outcomes.
- `backend/src/jolt/ai_review_pack.py` — job-review export contract.
- `backend/src/jolt/review_inbox_exchange.py` — current sequential reasoning protocol embedded in exported package.
- `backend/src/jolt/ai_review_import.py` — AI review schema/import validator and deterministic conflict gate.
- `backend/src/jolt/hardline_evidence.py`, `employment_geography.py` — deterministic eligibility evidence; high-impact, regression-sensitive.
- `backend/src/jolt/unified_ai_work_package.py` and `*_exchange.py` — unified ChatGPT round-trip system.
- `backend/src/jolt/market_*` — Market Intelligence.
- `backend/src/jolt/linkedin_command_center.py` and related capture files — LinkedIn Profile/Connections/activity intelligence.
- `backend/tests/` — backend regression/contract tests. Inspect neighboring tests before changing behavior.
- `backend/pyproject.toml` — Python dependencies/tooling; note package version currently differs from FastAPI app version.

## Frontend
- `frontend/src/Workbench.tsx` — top-level section orchestration/navigation where present.
- `frontend/src/App.tsx` — core application UI composition.
- `frontend/src/ApplicationDashboard.tsx` and `Application*` — Applications UI.
- `frontend/src/ProfessionalIntelligence*` — Capture Jobs / Professional capture UI.
- `frontend/src/LinkedInCommandCenter*` — LinkedIn Profile/Connections UI.
- `frontend/src/MarketIntelligence*` — Market Insights UI.
- `frontend/src/DataTools*` — Settings & Data, exports/imports/preferences.
- `frontend/src/*.test.tsx` — component/workflow regressions.
- `frontend/package.json` — frontend dependencies/scripts.

## Runtime / Windows operation
- `tools/start-jolt.ps1`, `tools/stop-jolt.ps1`, `tools/validate-jolt.ps1` — preferred controlled local lifecycle/diagnostics.
- `START_JOLT.bat`, `JOLT.ps1`, related root launchers — Windows convenience entrypoints retained in repo.
- `.jolt/` — local runtime PID/log state (generated, not project memory).
- `UPDATE_JOLT_ENVIRONMENT.bat` — local dependency/environment refresh helper.

## CI / certification
- `.github/workflows/ci.yml` — core backend/frontend checks.
- `.github/workflows/playwright-acceptance.yml` — browser acceptance gate.
- `.github/workflows/full-cycle-playwright-certification.yml` — full-cycle supported UI/workflow gate.
- `.github/workflows/windows-launcher-contract.yml` — launcher validation.

## High-value docs
- `docs/domain-model.md`
- `docs/jolt-architecture-audit-20260729.md`
- `docs/automation-and-testing.md`
- `docs/backup-and-restore.md`
- `docs/jolt-chatgpt-feedback-roadmap-20260901.md`
- `docs/configurable-evaluation-strategy.md`
- dated capture/certification docs: historical evidence; confirm current source before treating them as present behavior.

## Generated/exported data
AI work packages, capture JSON/ZIP archives and validation bundles are runtime/export artifacts and should not become the source of truth for code state. Use them as acceptance evidence, then persist conclusions/status in `.ai/`.