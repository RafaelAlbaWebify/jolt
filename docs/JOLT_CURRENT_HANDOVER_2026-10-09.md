# JOLT current handover — 2026-10-09

> Read this first with `.ai/SESSION_PROTOCOL.md`, `.ai/PROJECT_STATE.json`, and `.ai/KNOWN_ISSUES.md`. This is a reconciliation record, not a replacement for canonical state. Runtime and exact-head CI outrank this document.

## Why this file exists
The team continued source adapter work in PRs #510–#522 without updating canonical `.ai/` project memory. As of 2026-10-09, `.ai/CONTEXT.md` still describes 2026-10-03 and `.ai/TEST_STATUS.json` still describes 2026-09-30. This is a workflow failure; all future sessions must read and reconcile canonical state before making changes.

## Product boundary and data safety
- Local-first Windows x64 JOLT with SQLite. Protect human review decisions and Applications state above captures.
- Never operate on production data destructively. Current normal intelligence loop uses the Unified AI Work Package.
- Do not claim a source adapter is production-ready on CI alone; live and persistence acceptance are distinct.

## Evidence-verified source status

### LinkedIn
Previously certified saved-search/frozen discovery and Unified AI Work Package workflow; do not infer all other LinkedIn modules or currently running state are healthy without checking runtime.

### Indeed — capture acceptance
- PRs #510–#519 corrected search/identity, instrumentation and the missing-selector 26-second latency.
- Actual supervised run on 2026-10-09, 40 offers across four observed pages, 40/40 verified, ~3.99 sec/job mean, 26 new and 14 recognized duplicates; stopped after only repeated identities were observed on page 4. Evidence ZIP: `JOLT_INDEED_CHROME_CAPTURE_20261009_110952.zip`.
- Read-only artifact-vs-source persistence audit tool added in PR #520, merged main `63ce2975c78cce1b40f65929d62b7550ce04b8c7`. User actually ran it: capture run `79bd509f-742d-432e-9bb5-b6ab9eb418f5`, 40 expected/40 checked/40 passed, zero errors.
- **Proven:** capture speed, observed pagination, internal artifact and source_document consistency, and linked postings for this run.
- **Not proven:** word-for-word live-site description fidelity; normalized Posting.description equality; guaranteed future resilience to layout changes.
- No reason to keep changing Indeed speed without a measured regression.

### InfoJobs — BLOCKED on real access
- PR #521 foundation merged `d4f99edfffc45f09cf50d7672f854d7758f0b155`.
- PR #522 authenticated read-only preview merged `556d3e391c16e29199f13569690397870f4b7b15` after 8/8 green CI.
- User **does not have an InfoJobs developer Client ID or Client Secret**. Do NOT suggest running an authenticated live API test until access is granted. Do NOT ask user to paste secrets in chat.
- Implemented code is not validated against live API responses and does not ingest InfoJobs results to SQLite or provide a UI workflow.
- Next action: verify current registration and developer access eligibility using official documentation; if access is impractical, make explicit go/no-go choice between supervised browser read-only flow and shifting effort to an accessible portal. Avoid speculative builds predicated on unavailable credentials.
- Before touching the adapter again, review assumptions about API schema/authentication using authoritative current docs. Unit tests only mock responses.

### Tecnoempleo and Welcome to the Jungle
- No implemented source adapters as of this handover. API access/terms and suitability for a supervised operator workflow must be established first.
- Don't label them operational or imply access has been obtained.

## Roadmap, ordered by evidence and dependencies
1. **P0 — Repair canonical project-memory drift**: reconcile `.ai/PROJECT_STATE.json`, `.ai/CONTEXT.md`, `.ai/KNOWN_ISSUES.md`, `.ai/ROADMAP.md`, `.ai/TEST_STATUS.json` with exact evidence above; ensure session protocol includes a mandatory gate before merging PRs. This handover is an interim bridge, not completion.
2. **P1 — Decide InfoJobs access strategy**: official developer registration and terms, time/availability constraints, and an accessible fallback if unavailable. Document decision.
3. **P2 — End-to-end InfoJobs acceptance**: only once access path exists, one real supervised bounded run through detail identity -> artifact -> ingestion -> persistence audit, with existing decisions/applications protected.
4. **P3 — Select and implement next two portals** based on lawful/available access and actual user job-search coverage, not presumed API availability.
5. **P4 — Operational polish**: `start-jolt.ps1` currently reinstalls ~170 npm packages repeatedly (22–55 seconds observed). Investigate independently after source path is unblocked; preserve clean-install reproducibility.

## Definition of done for a source
Authenticated/authorized or supervised compliant access works on the operator's PC; real multi-page coverage tested; identity/title/company/location/description verified; ingestion deduplicates correctly; read-only persistence audit passes; relevant CI gates green; no human/application state regressions. A parser-only PR is **foundation**, not a finished integration.

## Handover procedure
1. Read canonical `.ai/` files AND this file.
2. Check live repo HEAD, active PRs, exact-head CI, local runtime commit and any user-supplied recent ZIP.
3. Explicitly list what is measured vs assumed.
4. Make one bounded change and test it; do not roll into the next portal before closing or explicitly blocking the current one.
5. Update canonical `.ai/` files **in the same PR** as any substantive status change; keep unverified and blocked work visible.
