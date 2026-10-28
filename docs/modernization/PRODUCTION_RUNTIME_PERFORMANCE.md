# Production runtime performance — October 28, 2026

## Observed local baseline (248 MiB SQLite; operator JOLT_RUNTIME_ACCEPTANCE.zip)
- Health endpoint: 1.97 ms median, HTTP 200.
- Opportunity index: 3.314 s median, HTTP 200.
- Review Inbox legacy export: 103.419 s median (99.894–107.094 s), HTTP 200.
- Market Intelligence: 3/3 timed out.
- Unified AI work package export: 3/3 timed out.
- Frontend HTTP: HTTPError; prior probe omitted status; Chromium smoke not attempted.
These are real operator observations, **not** locally reproduced by GitHub CI.

## Changes in this iteration
- Semantic duplicate groups indexed by normalized vacancy title. Comparisons between unrelated titles removed while canonical priority and group order remain unchanged.
- Manual market evaluations query restricted to the manual posting IDs rather than all historical evaluations.
- Duplicate Review Inbox text sanitization removed for language and preanalysis stages.
- Safe stage timers added for the actual Review Inbox legacy export, Review Inbox bundle stages, and each unified AI exchange section.
- The operator ZIP collects only numeric stage readings and the frontend HTTP status. It excludes raw job descriptions, source URLs, API content and log lines.

## Practical operator targets (guidance, not synthetic CI pass criteria)
- Frontend initial HTTP navigation: 2xx and Chromium initial navigation without JS page errors.
- Opportunity index: median below 5 seconds on the current Windows machine.
- Market Intelligence: return HTTP 200 within 15 seconds on the full real database.
- Review Inbox legacy export: median below 15 seconds on the current data.
- Unified AI export: return HTTP 200 within 30 seconds on the current data.
Targets may be refined based on payload volume and actual workflows. Any timeout or HTTP error is a failure, regardless of CI results.

## Verification and next diagnosis
1. Merge only after exact-head CI green.
2. Restart JOLT through the normal supervised process to ensure the running backend has the merged code. Check loaded checkout revision.
3. Run `pwsh -NoProfile -File tools/accept-jolt-runtime.ps1` and submit `JOLT_RUNTIME_ACCEPTANCE.zip`.
4. Inspect `performance_stages` to identify each remaining expensive phase, particularly the legacy Review Inbox data load/transformation and unified section timing.
5. If targets are still not met, implement only the verified bottleneck and repeat on the same machine/data. Do not certify performance from unit tests or CI.

No cleanup, migration, mutation or purge of the production database is part of this work.
