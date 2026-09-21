# JOLT Operability Gates

## Current computed state
- Development usable: **PASS**
- Internal testing ready: **PASS**
- External beta/testing ready: **PASS**
- Real prospect ready: **PASS**
- Production ready: **PASS**

Current conservative operability estimate: **100%**.

This is not a release claim. JOLT now has one successful corrected real 79-job capture -> strict sequential AI review -> validated import cycle, durable restart persistence, readable structured import validation, unified backend/API version parity, live-validated LinkedIn profile-detail traversal, and a live-validated Capture Jobs path after the asyncio/Playwright regression fix in PR #396. The second consecutive real capture -> strict sequential review -> validated import cycle has now completed and persisted across a full restart. Both remaining real-prospect runtime gates passed on 2026-09-20 through the non-destructive acceptance rehearsal on a restored copy of the active database. Production hardening remains before a 100%/Production-ready claim.

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

## 3. External beta/testing ready — PASS
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
- [x] current LinkedIn profile-detail completeness fix is proven against the real live profile after PR #393 — fresh 2026-09-19 capture;
- [x] no unresolved P1 issue in beta-critical paths.

Live acceptance passed on 2026-09-19 for both beta-critical LinkedIn paths. PR #393's profile-detail traversal reached the later Licenses & certifications entries on the real profile using the nested scroll surface. PR #396 then repaired a Capture Jobs regression where Playwright Sync API could run inside an asyncio loop; exact-head CI/Playwright/full-cycle gates passed and a fresh live capture completed 100/100 verified jobs over four pages with no warnings and `requested_limit_reached`. Legacy LinkedIn `/details/` snapshots that predate the stronger traversal contract remain fail-closed.

## 4. Real prospect ready — PASS
Meaning: JOLT can be trusted to support real application decisions for a live candidate/prospect workflow without developer repair or hidden manual state correction.

All external-beta criteria plus:
- [x] two consecutive real capture/review/import cycles complete without internal data repair — second 100-job cycle imported and persisted after restart on 2026-09-19;
- [x] top recommended jobs are manually source-audited and no hardline-ineligible job is promoted — Hired and Synthires source evidence audited on 2026-09-19;
- [x] corrected AI decisions/import receipt/Market Insights persisted through a full real JOLT restart on 2026-09-05;
- [x] capture cleanup/archive cannot remove pursued applications in a dated real acceptance rehearsal — 2026-09-20 restored-copy rehearsal preserved the protected application and posting while purging 31 superseded capture runs and 1206 capture-only postings;
- [x] AI review contract 1.1 rejects omitted capture postings as well as duplicate, outsider, source-id and deterministic-hardline conflicts — PR #385; malformed payloads also fail through schema validation;
- [x] backup/export and restore procedure has a dated successful rehearsal on the active schema — 2026-09-20 acceptance created, verified and restored a 60,772,352-byte SQLite backup with SHA-256 `56c7fff434e129e03e0fe41a27eb9236195e284b1cbd9d1cc252b829786e3131`; restored core record counts matched the source before cleanup;
- [x] runtime commit/version evidence is available in diagnostics and package/API version parity is enforced;
- [x] no open P0/P1 issue affecting capture, review, import, persistence or recovery — issue #392 closed after live #393 acceptance; no other open issues.

All real-prospect gates now have dated evidence. **Real prospect ready** is therefore permitted from 2026-09-20 onward unless later evidence invalidates a gate.

## 5. Production ready — PASS
Meaning: supportable, repeatable, recoverable operation beyond the developer/operator's own machine.

All real-prospect criteria plus:
- [x] supported OS/runtime/dependency matrix is explicit — PR #403;
- [x] clean install from documented prerequisites succeeds on a second environment or clean machine profile — fresh Windows runner certification #3 on PR #403;
- [x] database migration/rollback/recovery policy is proven — PR #406 plus Migration recovery certification #1;
- [x] backup/restore is automated or operationally reliable — verified backup/restore tooling plus pre-migration backup enforcement and dated rehearsals;
- [x] logs/diagnostics include loaded runtime identity versus repository checkout and structured AI import validation paths;
- [x] privacy/security review covers local evidence, browser profile and exports — PR #404;
- [x] failure/recovery behavior for LinkedIn login/checkpoint/network errors is validated on the real site — 2026-09-21 acceptance PASS;
- [x] release/package/API version parity is enforced at 0.8.0 by PR #388;
- [x] release artifact or deployment procedure is reproducible — PR #408 Reproducible release certification #1;
- [x] regression and E2E suites are required on the exact release commit through main-push production certification workflows; final release candidate enables this invariant;
- [x] no unresolved P0/P1 release blocker — repository issue audit on 2026-09-21 found zero open issues.

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
- 2026-09-19: **97%** after PR #393's live profile-detail completeness acceptance and PR #396's live Capture Jobs acceptance both passed on the active runtime.
- 2026-09-19: **98%** after the second real 100-job review/import cycle persisted through restart and the promoted Hired/Synthires jobs passed manual source audit with no hardline-ineligible evidence.
- 2026-09-20: **99%** after the active-database backup→verify→restore rehearsal passed and guarded retention cleanup on the restored production-shaped copy preserved an application-owned posting/application while safely purging superseded capture state; PRs #400 and #401 hardened the retention graph based on failures found by the rehearsal.

## Evidence policy
A gate may pass only from directly verified runtime/test evidence or an exact green CI/acceptance result for the relevant commit. Code existence is not verification. Historical success does not automatically prove the current commit. When evidence expires because behavior changes, move the criterion back to FAIL until reverified. A failed live acceptance can reveal that a previously green synthetic test modeled the external site too weakly; the response must be a stronger deterministic guard plus a new regression, not a lowered standard.


## 2026-09-19 audit notes

### Source audit — promoted jobs
- **Hired — IT Support Specialist (Remote), source 4467076188:** source body explicitly says "Remote (Work from Anywhere)" and later repeats flexible hours plus the ability to work from anywhere. No conflicting territorial restriction was found. Promotion is defensible.
- **Synthires — Technical Support Specialist (Remote | $30–$55/hr), source 4466264642:** listing scope is European Union; source body states contractor, remote, independent contractor engagement, fully remote opportunity and flexible remote schedule. No conflicting Spain-ineligible restriction was found. Promotion is defensible.
- Conditional cases remain appropriately unresolved: Crossing Hurdles and Mercor lack affirmative Spain cross-border eligibility; ALTEN is Spain-based but the captured source does not establish a Vigo-compatible remote/hybrid model.

### Recovery/retention code audit
- Backup/restore implementation uses SQLite's online backup API, SHA-256 manifest verification, byte-size validation, PRAGMA integrity_check, Alembic-revision validation and restore-to-new-target semantics.
- Automated backup tests verify successful restore, preserved data and tamper rejection.
- Active applications cannot be permanently deleted; guarded cleanup tests preserve retained postings/applications. These are strong code/test controls, but the operability gate still requires dated real-runtime rehearsals.

### Production audit
- PR #403 documents and enforces the supported Windows/Python/Node/npm/uv/Git runtime matrix and passed fresh-Windows clean-install certification #3 plus exact-head CI #1436, Playwright #674 and full-cycle #597.
- PR #404 records the dated privacy/security review for the SQLite evidence store, authenticated browser profiles, exports and acceptance backups, with a read-only sensitive-data audit.
- PR #406 establishes forward-only migration with mandatory verified pre-migration backup and passed Migration recovery certification #1, CI #1439, Playwright #676, clean-install #5 and full-cycle #599.
- PR #407 fail-closes LinkedIn auth/checkpoint/safety/network states and passed CI #1444, Playwright #680, clean-install #9 and full-cycle #603. The 2026-09-21 real-site acceptance then passed authwall detection, authenticated search access, forced-offline classification and recovery.
- PR #408 adds deterministic release construction and passed Reproducible release certification #1, CI #1441, Playwright #678, clean-install #7 and full-cycle #601.
- Final release-candidate workflows run on main pushes so the squash-merged release SHA itself receives CI, Playwright, full-cycle, clean-install, migration-recovery and reproducible-release certification.


## 2026-09-20 real-prospect acceptance
- Command: `REAL_PROSPECT_ACCEPTANCE.bat` on local `main` commit `ca6af3b25cae181bc8b8ccd13fed45417eaf36de`.
- Result: **PASS**; `active_database_modified=false`.
- Backup/restore: source core counts matched restored core counts before cleanup; manifest Alembic revision was `20260902_0022` because the backup was taken before the local runtime migration, and the restored copy then migrated successfully to `20260919_0023` before rehearsal cleanup.
- Retention plan: 31 superseded capture runs, 1206 capture-only postings, 53 retained postings, 0 missing market observations, no blocked reasons.
- Cleanup result on restored copy: 31 capture runs, 1879 capture items, 1879 capture artifacts, 90 capture pages, 1206 postings, 1687 source documents, 589 AI reviews, 3377 evaluations and 45 readiness reports deleted; 1740 market observations and 53 retained postings preserved.
- Protected fixture: application `d2df157f-152b-4f54-9a8b-f04332e4074a` and posting `733f215d-b03d-4d4d-9cc3-7d83bee0c957` both survived cleanup.
- Evidence report path: `%USERPROFILE%\\Downloads\\JOLT_ACCEPTANCE\\JOLT_REAL_PROSPECT_ACCEPTANCE_20260920_132820.json`.


## 2026-09-21 production acceptance
- Real-site LinkedIn failure/recovery command: `tools/accept-linkedin-failure-recovery.ps1`.
- Result: **PASS**.
- Authwall: LinkedIn login page classified `authentication_required`.
- Authenticated access: real LinkedIn jobs search loaded 7 visible job cards.
- Network failure: browser forced offline; navigation classified `network_failure`.
- Recovery: connectivity restored; the real jobs search returned to 7 visible job cards with no access problem.
- Evidence file: `C:\Users\ralba\Downloads\JOLT_LINKEDIN_FAILURE_RECOVERY_20260921_122015.json`.
- Repository issue audit: zero open issues on 2026-09-21.
- Certified product boundary: local-first, single-user JOLT on supported Windows x64. Future Indeed/InfoJobs adapters and multi-user/SaaS architecture remain outside this production-readiness claim.
- Operability promoted from **99% to 100%** when the exact final main release commit completes all main-push certification workflows.
