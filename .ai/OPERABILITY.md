# JOLT Operability Gates

## Current computed state
- Development usable: **PASS**
- Internal testing ready: **PASS**
- External beta/testing ready: **FAIL**
- Real prospect ready: **FAIL**
- Production ready: **FAIL**

Current conservative operability estimate: **96%**.

This is not a release claim. JOLT now has one successful corrected real 79-job capture -> strict sequential AI review -> validated import cycle, durable restart persistence, readable structured import validation, unified backend/API version parity, and stronger LinkedIn candidate-evidence selection. A second-cycle preparation uncovered a real profile-evidence defect: Licenses & certifications could be marked complete after an absolute footer jump while later lazy-loaded credentials were never traversed. PR #390 now traverses profile details progressively and fail-closes legacy non-progressive detail captures, but live LinkedIn recapture is still required before that P1 acceptance gap is closed.

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

Internal testing remains valid. Current work is acceptance hardening of live LinkedIn detail completeness and the second real AI round trip, not absence of the underlying workflows.

## 3. External beta/testing ready — FAIL
All must pass:
- [x] controlled startup and shutdown documented;
- [x] core capture/review/application workflows implemented;
- [x] real LinkedIn capture verified at least once;
- [x] source evidence and export/import contracts exist;
- [x] deterministic geography parser correction merged and exact-head gates green — PR #380;
- [x] corrected real capture -> sequential AI review -> import loop completed successfully on the active runtime on 2026-09-05;
- [x] runtime identity/staleness is obvious enough that a tester cannot unknowingly test old code — PR #384 plus runtime restart acceptance;
- [x] durable AI round-trip status/import receipt exists — PR #382 and runtime persistence acceptance;
- [x] LinkedIn Connections partial/complete semantics and bounded-sample AI metadata are merged — PR #377;
- [x] release/package/API version parity is enforced at 0.8.0 — PR #388;
- [ ] current LinkedIn profile-detail completeness fix is proven against the real live profile after PR #390;
- [ ] no unresolved P1 issue in beta-critical paths.

The current beta-critical P1 is the live acceptance of PR #390. Legacy LinkedIn `/details/` snapshots that predate progressive traversal are now rejected from candidate evidence instead of silently trusted.

## 4. Real prospect ready — FAIL
Meaning: JOLT can be trusted to support real application decisions for a live candidate/prospect workflow without developer repair or hidden manual state correction.

All external-beta criteria plus:
- [ ] two consecutive real capture/review/import cycles complete without internal data repair;
- [ ] top recommended jobs are manually source-audited and no hardline-ineligible job is promoted;
- [x] corrected AI decisions/import receipt/Market Insights persisted through a full real JOLT restart on 2026-09-05;
- [ ] capture cleanup/archive cannot remove pursued applications in a dated real acceptance rehearsal, although automated regressions protect the invariant;
- [x] AI review contract 1.1 rejects omitted capture postings as well as duplicate, outsider, source-id and deterministic-hardline conflicts — PR #385; malformed payloads also fail through schema validation;
- [ ] backup/export and restore procedure has a dated successful rehearsal on the active schema;
- [x] runtime commit/version evidence is available in diagnostics and package/API version parity is enforced;
- [ ] no open P0/P1 issue affecting capture, review, import, persistence or recovery.

Do not use the phrase **real prospect ready** unless every checkbox is passed with dated evidence.

## 5. Production ready — FAIL
Meaning: supportable, repeatable, recoverable operation beyond the developer/operator's own machine.

All real-prospect criteria plus:
- [ ] supported OS/runtime/dependency matrix is explicit;
- [ ] clean install from documented prerequisites succeeds on a second environment or clean machine profile;
- [ ] database migration/rollback/recovery policy is proven;
- [ ] backup/restore is automated or operationally reliable;
- [x] logs/diagnostics include loaded runtime identity versus repository checkout and structured AI import validation paths;
- [ ] privacy/security review covers local evidence, browser profile and exports;
- [ ] failure/recovery behavior for LinkedIn login/checkpoint/network errors is validated on the real site;
- [x] release/package/API version parity is enforced at 0.8.0 by PR #388;
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
- 2026-09-05: **92%** after the first corrected real 79-job strict-sequential review/import cycle succeeded on the active runtime.
- 2026-09-05: **93%** after PR #387 made structured AI import failures actionable instead of rendering `[object Object]`.
- 2026-09-05: **95%** after the imported AI receipt, Market Insights and Review Inbox decisions survived a full local JOLT restart.
- 2026-09-05: **96%** after PR #388 unified backend package/API/runtime version parity at 0.8.0 with regression enforcement.
- 2026-09-05/06: PRs #389 and #390 materially harden LinkedIn candidate evidence but **do not increase the percentage yet** because real profile-detail completeness acceptance is still pending.

## Evidence policy
A gate may pass only from directly verified runtime/test evidence or an exact green CI/acceptance result for the relevant commit. Code existence is not verification. Historical success does not automatically prove the current commit. When evidence expires because behavior changes, move the criterion back to FAIL until reverified. A failed live acceptance can reveal that a previously green synthetic test modeled the external site too weakly; the response must be a stronger deterministic guard plus a new regression, not a lowered standard.
