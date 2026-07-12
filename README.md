# JOLT

JOLT is a local-first job-search decision, application-tracking, and market-intelligence workbench.

Its primary objective is to help the user obtain a suitable job. Its secondary objective is to turn real job-market and application-outcome evidence into practical career-development guidance.

This repository is a clean rebuild. The legacy `jolt-job-tracker` repository is reference material only and will not be used as the implementation foundation.

## Current capability

JOLT now has a tested local manual-intake workflow:

```text
paste job text
→ preserve source evidence
→ normalize the posting
→ detect duplicates
→ evaluate with a versioned profile
→ record a separate human decision
→ retain the opportunity in SQLite
```

The current evaluation rules are deliberately small and provisional. They prove the architecture; they are not yet claimed to represent a complete job-search strategy.

## Local development

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

GitHub Actions executes the same core checks for pull requests and `main`.

## Core principles

- Local-first and single-user initially.
- LinkedIn supervised capture is the first automated source.
- Manual opportunity intake remains a first-class input.
- Indeed and InfoJobs are planned source adapters after the base is stable.
- Human review remains authoritative.
- Evaluation rules must be configurable, versioned, explainable, and auditable.
- Capture, posting identity, evaluation, review, application, outcome, and market evidence are separate domain concepts.
- Automated tests, diagnostics, screenshots, logs, and CI are part of the product from the beginning.
- No credential storage, CAPTCHA bypass, auto-application, recruiter messaging, or unattended mass crawling.

See `docs/` for the product and architecture specifications.
