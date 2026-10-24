# JOLT Engineering Harness — v1 acceptance contract

## Scope and completion rule

The harness v1 is **complete** only when the exact PR head has green checks for the existing CI jobs (backend, frontend, Windows scripts), the change-impact contract workflow, and the required release/Playwright/migration workflows. A green earlier commit does **not** certify a new head. The operator's modified local checkout is outside that remote certification.

The harness is an engineering safety net, **not** proof that JOLT is operational end to end. Indeed recovery, LinkedIn capture limits and production behavior are separately tracked application work.

## Gate ownership (single source per concern)

| Concern | Authoritative check | Duplicate work prohibited |
|---|---|---|
| Python lint, format, typing, backend tests | `.github/workflows/ci.yml` backend | Do not rerun full backend suite in impact workflow |
| React tests, security audit, build | `.github/workflows/ci.yml` frontend | Do not duplicate frontend suite |
| PowerShell parsing and command contracts | `.github/workflows/ci.yml` windows-scripts | Do not run scripts against operator data |
| Impact evidence, capture contract drift, mutation/negative controls | `.github/workflows/change-impact-contract.yml` analyzer | Do not execute full app suites here |
| Release, Playwright, migration recovery | Existing corresponding workflows | Preserve as separate domain certifications |
| Local operator data and ZIP recovery | Explicit read-only preflights, operator approved follow-on | Never infer from GitHub CI |

`tools/dev-preflight.ps1` is the standard local full preflight for changes. `tools/local-quality-gate.ps1` remains a narrower backend/database integrity check and must not be advertised as equivalent to full PR certification.

## Negative controls (must pass)

1. Known compatible limits: no detected conflict.
2. Artificially change LinkedIn producer 100/10 → 200/20 against 100/10 receiver: detect three mismatches.
3. Remove shared limits configuration: report unknown, do not claim compatibility.
4. Remove a Python import in a temporary fixture: reverse dependency and impacted test disappear, proving graph is driven by evidence.

These mutate **only temporary test fixtures**, not repository source, live database, captures, or users' profiles.

## Definition of done

- [ ] Exact-head GitHub jobs are green, including negative controls.
- [ ] Impact JSON artifact is produced on PRs and reviewed for `warnings`, `unresolved_relationships`, `capture_contract_risks`.
- [ ] New behavior-changing contracts have direct tests in the owning suite, and existing workflows run them.
- [ ] No real DB, ZIP, backup, or operator state is modified during harness certification.
- [ ] Merge only after the above conditions, with explicit limitations recorded.

## Known limitations

Static cross-language mapping cannot prove all runtime FastAPI routes, dynamically built fetch URLs, database transaction semantics, or PowerShell subprocess behavior. Negative controls demonstrate sensitivity to **specific** regressions, not complete detection of all regressions. Missing shared limits are reported as unknown; no claim of LinkedIn 200/20 support is permitted without live and local integration tests. An operator working tree with uncommitted changes is not automatically certified by CI.

## Out-of-scope follow-up

- Indeed: the preserved 161-item ZIP passed read-only preflight; import remains separate and requires backup, duplicate safeguards and repeat-run verification.
- LinkedIn: reconcile the local shared limits (currently 200/20) with real capture/receiver (100/10) before raising any caps.
- Application feature bugs should become contract tests in the owning suite, not endlessly widen this harness.
