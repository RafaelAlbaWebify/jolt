# JOLT Automation and Testing Strategy v0.1

## Goal

Normal development must not depend on repeatedly asking the user to download one-off PowerShell files, run ad hoc tests, and upload reports.

The repository must provide stable, reusable automation from the beginning.

## Development model

```text
Repository change
→ automated local/CI verification
→ logs, screenshots, and artifacts
→ patch based on evidence
→ rerun verification
→ user involvement only when required
```

## Work that should be automated

- Dependency installation and reproducible environment setup.
- Backend and frontend builds.
- Unit, integration, contract, and end-to-end tests.
- Database creation and migrations.
- Synthetic and fixture-based capture tests.
- JOLT UI screenshots and visual review artifacts.
- API smoke tests.
- Log collection.
- Diagnostic and analysis-pack generation.
- Security and secret scans.
- Linting, formatting, and type checks.
- GitHub Actions checks on pull requests.

## Work that requires the user

- First-time authenticated LinkedIn login in a local persistent browser profile.
- CAPTCHA or source-side security prompts.
- Final Windows-specific packaging verification.
- Subjective product and UX decisions.
- Approval of changes to evaluation constraints, preferences, and strategic priorities.
- Confirmation before external writes or actions.

## Test layers

### Unit tests

Verify pure domain behavior:

- URL normalization.
- Identity matching rules.
- State transitions.
- Profile versioning.
- Evaluation rules.
- Requirement extraction helpers.
- Market aggregate calculations.

### Integration tests

Verify:

- API plus application service plus SQLite.
- Transactional writes.
- Duplicate handling.
- Evaluation persistence.
- Review and application creation.
- Analysis-pack export.

### Contract tests

Every source adapter must produce the same canonical contracts:

- ListingCandidate.
- CapturedOpportunity.
- CaptureDiagnostics.
- DetailCaptureResult.

### Fixture-based adapter tests

Use sanitized saved HTML/JSON fixtures to prove selectors and mapping without accessing external sites.

### End-to-end tests

Use synthetic data and JOLT's own UI to prove:

```text
intake → normalize → evaluate → review → persist → export
```

### Supervised live-source tests

Run locally and only when explicitly requested. They must be bounded and produce evidence:

- screenshots
- interaction log
- adapter diagnostics
- captured identifiers
- failures
- redacted ZIP report

They are not required for every CI run.

## Permanent local commands

The implementation phase should provide stable commands such as:

```text
tools/setup.ps1
tools/dev.ps1
tools/test.ps1
tools/ui-audit.ps1
tools/linkedin-capture-test.ps1
tools/diagnostics.ps1
tools/rollback.ps1
```

These files live in the repository and are improved in place. The user should not repeatedly download replacement scripts.

## CI quality gates

A pull request should not be considered verified unless all applicable checks pass:

- backend formatting/lint
- backend type checking
- backend unit/integration tests
- frontend formatting/lint
- frontend tests
- frontend production build
- end-to-end synthetic workflow
- migration smoke test
- secret scan

## Artifacts

Failed CI or local verification should produce:

- machine-readable test results
- application logs
- screenshots where relevant
- Playwright traces where relevant
- database/schema information
- environment/version summary

## External-source safety

- No credentials in source control, logs, fixtures, CI variables, screenshots, or exports.
- Live adapters are disabled in CI unless a deliberately configured safe test exists.
- No CAPTCHA solving or authentication bypass.
- Rate, page, and detail limits are mandatory.
- Capture must support dry-run and fixture modes.
- A clicked listing must be verified against the expected source job ID before detail text is accepted.

## Definition of proof for the first vertical slice

Automatic proof must show that:

1. A source document is preserved.
2. A posting candidate is normalized with evidence.
3. A duplicate candidate is separated from evaluation.
4. An evaluation records profile and engine versions.
5. A human review decision is persisted separately.
6. A pursued posting can create an application.
7. Data survives an application restart.
8. An analysis ZIP can be produced.
9. The same test passes on Windows-compatible local tooling and GitHub CI.
