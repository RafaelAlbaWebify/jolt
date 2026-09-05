# JOLT Operability Gates

## Current computed state
- Development usable: **PASS**
- Internal testing ready: **PASS**
- External beta/testing ready: **FAIL**
- Real prospect ready: **FAIL**
- Production ready: **FAIL**

Current conservative operability estimate: **72%**. This is not a release claim; it reflects that the main local workflows exist and are heavily tested, while a real AI round trip is still waiting on a deterministic-evidence correction and several reliability/UX workstreams remain open.

## 1. Development usable — PASS
Required:
- repository builds/starts through documented local workflow;
- FastAPI/React source and migrations exist;
- temporary/test databases are supported;
- core domain workflows have automated coverage;
- developers can inspect runtime logs/diagnostics.

Evidence: README launcher/manual-development paths, backend/frontend tests, `.github/workflows/`, validation tooling.

## 2. Internal testing ready — PASS
Required:
- clean developer setup documented;
- backend and frontend can start together;
- real supervised external input can be captured;
- persistence and capture provenance exist;
- CI + browser acceptance infrastructure exists;
- no known P0 blocker preventing operator testing.

Current note: internal testing remains valid despite KI-001 because the issue has a defined workaround and is being fixed; it prevents higher readiness, not controlled development/testing.

## 3. External beta/testing ready — FAIL
All must pass:
- [x] controlled startup and shutdown documented;
- [x] core capture/review/application workflows implemented;
- [x] real LinkedIn capture verified at least once;
- [x] source evidence and export/import contracts exist;
- [ ] latest deterministic geography parser correction merged and green;
- [ ] corrected real capture -> sequential AI review -> import loop completed successfully;
- [ ] runtime identity/staleness is obvious enough that a tester cannot unknowingly test old code;
- [ ] PR #376 round-trip status/receipt UX resolved or an equivalent durable acceptance mechanism exists;
- [ ] LinkedIn Connections partial/complete semantics are merged and validated if network analysis is included in beta scope;
- [ ] no unresolved P1 issue in beta-critical paths.

## 4. Real prospect ready — FAIL
Meaning: JOLT can be trusted to support real application decisions for a live candidate/prospect workflow without developer repair or hidden manual state correction.

All external-beta criteria plus:
- [ ] two consecutive real capture/review/import cycles complete without internal data repair;
- [ ] top recommended jobs are manually source-audited and no hardline-ineligible job is promoted;
- [ ] rejected/conditional/pursued transitions persist through restart;
- [ ] capture cleanup/archive cannot remove pursued applications;
- [ ] AI update import rejects malformed, incomplete, outsider, duplicate and deterministic-conflict payloads;
- [ ] backup/export and restore procedure has a dated successful rehearsal on the active schema;
- [ ] runtime/version evidence is recorded in support/validation output;
- [ ] no open P0/P1 issue affecting capture, review, import, persistence or recovery.

Do not use the phrase **real prospect ready** unless every checkbox is passed with dated evidence.

## 5. Production ready — FAIL
Meaning: supportable, repeatable, recoverable operation beyond the developer/operator's own machine.

All real-prospect criteria plus:
- [ ] supported OS/runtime/dependency matrix is explicit;
- [ ] clean install from documented prerequisites succeeds on a second environment or clean machine profile;
- [ ] database migration/rollback/recovery policy is proven;
- [ ] backup/restore is automated or operationally reliable;
- [ ] logs/diagnostics are adequate for support incidents;
- [ ] privacy/security review covers local evidence, browser profile and exports;
- [ ] failure/recovery behavior for LinkedIn login/checkpoint/network errors is validated;
- [ ] release/versioning authority is unified;
- [ ] release artifact or deployment procedure is reproducible;
- [ ] regression and E2E suites are green on the exact release commit;
- [ ] no unresolved P0/P1 release blocker.

## Evidence policy
A gate may pass only from directly verified runtime/test evidence or an exact green CI/acceptance result for the relevant commit. Code existence is not verification. Historical success does not automatically prove the current commit. When evidence expires because behavior changes, move the criterion back to FAIL until reverified.