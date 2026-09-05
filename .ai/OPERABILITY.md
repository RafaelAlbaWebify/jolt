# JOLT Operability Gates

## Current computed state
- Development usable: **PASS**
- Internal testing ready: **PASS**
- External beta/testing ready: **FAIL**
- Real prospect ready: **FAIL**
- Production ready: **FAIL**

Current conservative operability estimate: **86%**.

This is not a release claim. Since the original 72% control-layer baseline, JOLT has removed several evidence-backed blockers: deterministic geography parsing was corrected, durable AI import/freshness UX was merged, LinkedIn Connections partial/complete semantics were hardened, stale loaded-backend code now produces an operator-visible stop warning, and AI review contract 1.1 now rejects omitted capture postings deterministically. The remaining blocker for external beta is the corrected real 79-job review/import round trip on the current runtime.

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

Current note: internal testing remains valid. The outstanding P1 is completion of the corrected real AI round trip, not absence of the underlying workflow.

## 3. External beta/testing ready — FAIL
All must pass:
- [x] controlled startup and shutdown documented;
- [x] core capture/review/application workflows implemented;
- [x] real LinkedIn capture verified at least once;
- [x] source evidence and export/import contracts exist;
- [x] deterministic geography parser correction merged and exact-head gates green — PR #380;
- [ ] corrected real capture -> sequential AI review -> import loop completed successfully on the current runtime;
- [x] runtime identity/staleness is obvious enough that a tester cannot unknowingly test old code — PR #384;
- [x] durable AI round-trip status/import receipt exists — PR #382;
- [x] LinkedIn Connections partial/complete semantics and bounded-sample AI metadata are merged and exact-head gates green — PR #377;
- [ ] no unresolved P1 issue in beta-critical paths.

The remaining beta-critical P1 is KI-005: the corrected stored 79-job capture has not yet completed a successful import round trip after all deterministic fixes.

## 4. Real prospect ready — FAIL
Meaning: JOLT can be trusted to support real application decisions for a live candidate/prospect workflow without developer repair or hidden manual state correction.

All external-beta criteria plus:
- [ ] two consecutive real capture/review/import cycles complete without internal data repair;
- [ ] top recommended jobs are manually source-audited and no hardline-ineligible job is promoted;
- [ ] rejected/conditional/pursued transitions persist through restart;
- [ ] capture cleanup/archive cannot remove pursued applications;
- [x] AI review contract 1.1 rejects omitted capture postings as well as duplicate, outsider, source-id and deterministic-hardline conflicts — PR #385; broader malformed-payload validation remains covered by Pydantic/schema tests;
- [ ] backup/export and restore procedure has a dated successful rehearsal on the active schema;
- [x] runtime commit/version evidence is available in runtime diagnostics;
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

## Operability progression
- 2026-09-05: **72%** control-layer baseline.
- 2026-09-05: **75%** after PR #380 deterministic geography correction.
- 2026-09-05: **78%** after PR #382 durable AI round-trip UX.
- 2026-09-05: **81%** after PR #377 Connections capture/quality hardening.
- 2026-09-05: **84%** after PR #384 stale-runtime guard.
- 2026-09-05: **86%** after PR #385 exact-set AI review import enforcement.

## Evidence policy
A gate may pass only from directly verified runtime/test evidence or an exact green CI/acceptance result for the relevant commit. Code existence is not verification. Historical success does not automatically prove the current commit. When evidence expires because behavior changes, move the criterion back to FAIL until reverified.
