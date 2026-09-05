# JOLT

JOLT is a local-first job-search evidence, application-tracking, and market-intelligence workbench.

Its purpose is to capture, preserve, structure, and expose trustworthy job-search evidence so the user can make better-informed decisions. JOLT does not authoritatively decide whether to apply, reject an opportunity, rank career priorities, or prescribe career-development actions; those judgments remain with the human user and, when desired, an external reasoning layer such as ChatGPT.

This repository is a clean rebuild. The legacy `jolt-job-tracker` repository is reference material only and will not be used as the implementation foundation.

## AI project control

Repository state is the authoritative project memory. Future AI/development sessions must start with `.ai/CONTEXT.md`, `.ai/PROJECT_STATE.json`, `.ai/KNOWN_ISSUES.md`, and `.ai/OPERABILITY.md`, then inspect the relevant source/tests for the active workstream. `PROJECT_MEMORY.md` remains the durable historical invariant ledger. Chat history is not a required bootstrap dependency.

Use `python tools/build_ai_context.py` to generate a deterministic current-head snapshot without overwriting manually maintained decisions/history.

## Current capability

JOLT now supports:

```text
manual or verified LinkedIn evidence
→ preserve source evidence
→ normalize and deduplicate the posting
→ retain explainable evaluation metadata and provenance
→ record a separate human decision
→ track the application and outcome
→ retain capture diagnostics in SQLite
→ aggregate market evidence
→ export the complete evidence chain
```

Any evaluation outputs retained by JOLT are evidence and provenance, not authoritative career decisions. Human review remains authoritative, and external reasoning may interpret JOLT evidence without changing the underlying source record.

## Controlled Windows startup

Prerequisites available in `PATH`:

- Git
- Node.js 22 or later
- npm
- `uv`

From the repository root:

```powershell
.\tools\start-jolt.ps1
```

The command automatically:

1. Synchronizes Python dependencies.
2. Applies Alembic database migrations.
3. Installs frontend dependencies.
4. Starts the backend and frontend.
5. Waits until both services respond.
6. Records process IDs and local logs under `.jolt`.
7. Opens `http://127.0.0.1:5173`.

Start JOLT and immediately begin a bounded supervised LinkedIn capture:

```powershell
.\tools\start-jolt.ps1 `
    -StartLinkedInCapture `
    -SearchUrl "https://www.linkedin.com/jobs/search/?keywords=IT%20Support" `
    -MaxJobs 10
```

Stop the local services:

```powershell
.\tools\stop-jolt.ps1
```

Create one validation ZIP directly in Downloads:

```powershell
.\tools\validate-jolt.ps1
```

The validation ZIP contains service reachability, prerequisite paths, process state, and local logs. It does not automatically open the Downloads folder.

## Manual development

Backend:

```powershell
cd backend
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn jolt.main:app --reload
```

Frontend, in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The frontend connects to `http://127.0.0.1:8000` by default. Set `VITE_API_BASE_URL` to override it.

## Verification

```powershell
cd backend
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest

cd ..\frontend
npm test
npm run build
```

GitHub Actions executes the same core checks for pull requests and `main`, plus Windows PowerShell parser validation for the permanent local commands.

## Core principles

- Local-first and single-user initially.
- LinkedIn supervised capture is the first automated source.
- Manual opportunity intake remains a first-class input.
- Indeed and InfoJobs are planned source adapters after the base is stable.
- JOLT captures and structures evidence; it does not own the final career judgment.
- Human review remains authoritative.
- Retained evaluation metadata must be versioned, explainable, and auditable.
- Capture, posting identity, evaluation provenance, review, application, outcome, and market evidence are separate domain concepts.
- Automated tests, diagnostics, screenshots, logs, and CI are part of the product from the beginning.
- No credential storage, CAPTCHA bypass, auto-application, recruiter messaging, or unattended mass crawling.

See `docs/` for the product and architecture specifications.
