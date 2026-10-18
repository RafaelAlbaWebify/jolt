# JOLT — Outcome-based improvement baseline (2026-10-18)

## Product objective
Deliver a reliable daily operator workflow across supported job portals: capture relevant jobs from a controlled saved-search queue, retain full descriptions and provenance, show reviewable opportunities, support truthful human decisions and track applications without contaminating genuine data.

## Evidence rules
- A passing GitHub CI suite validates specific automated checks; it **does not** prove authenticated external portal operation or time saved.
- GitHub repository inspections are source-level; operator Windows acceptance and saved-search outcomes require independent evidence.
- Do not present historical audit-register completion as operability, usefulness or architecture reduction.
- Do not run mutation-producing certification tests on the operator database; use disposable isolated state.

## Baseline scorecard (unknown means not measured)

| Outcome | Current verified baseline | Minimum next evidence |
|---|---|---|
| End-to-end daily workflow | Unknown (no full real-user run evidenced in this audit) | One bounded operator run, source→capture→review→decision→application, persisted after restart |
| Portal coverage (LinkedIn, Indeed, InfoJobs, Jobgether) | Real-world acceptance not established for all four | Per-portal dated accepted captures, full descriptions, links, provenance, explicit failure reports |
| Quality/relevance of reviewed opportunities | Unknown | Accepted relevant opportunities divided by inspected jobs, per portal and search |
| Operator time and intervention burden | Unknown | Baseline stopwatch for discovery, capture supervision, review and follow-up on real routine |
| Data integrity and privacy | Backup and restore false-success safeguards merged; remaining synthetic fixture/log issues noted | Disposable-data audit run, no lasting test fixtures in operator DB, backup restore negative-path test |
| Architecture footprint | Baseline 300 code/tool files, 2,405,104 Git-tree bytes (prior measurement); byte count is not LOC | Re-run at same commit after a specific simplification; preserve behavior/tests |
| Code removed without regressions | No confirmed integrated reduction as of initial baseline | Merge and verify alternate stop wrapper consolidation; diff + Windows checks |
| Critical unresolved operator risks | At least test-data contamination and PID-file-based force termination in full-cycle scripts still under investigation | Triage and contain without disrupting operator services |

## Next three milestones
1. **Safety release:** merge exact-head CI-green fail-closed changes to stop alias, UI audit and schema DB access; perform targeted Windows negative-path acceptance. Track actual reductions from Git diff.
2. **Daily workflow measurement:** on a copy or controlled environment, collect one end-to-end operator report (jobs captured, verified, reviewed, accepted, time spent, unexpected interventions, persistence after restart). Explicitly distinguish simulation from live portal evidence.
3. **Targeted simplification:** build a caller map for shutdown/preflight/AI-context tooling and propose one tested consolidation; reject deletions based only on naming similarity or selector collision.

## Decision rule
Pause sequential file-by-file audit batches unless a pending source is directly needed to resolve a known operational risk, trace a dependency or perform a measured simplification. Revisit the audit register only when it changes decisions.
