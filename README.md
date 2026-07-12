# JOLT

JOLT is a local-first job-search decision, application-tracking, and market-intelligence workbench.

Its primary objective is to help the user obtain a suitable job. Its secondary objective is to turn real job-market and application-outcome evidence into practical career-development guidance.

This repository is a clean rebuild. The legacy `jolt-job-tracker` repository is reference material only and will not be used as the implementation foundation.

## Current phase

Project foundation and specification. No production functionality is claimed yet.

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

See `docs/` for the working product and architecture specifications as they are added.
