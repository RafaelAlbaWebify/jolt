# JOLT closure baseline — 2026-10-13

## Product boundary
The local-first single-user Windows LinkedIn workflow has previously passed real capture, AI exchange, application-state preservation, backup/restore, and release certification. This is not a certification of multi-source operation.

**Closure target:** LinkedIn + Jobgether in the end-to-end operator flow. Indeed remains paused after portal blocking; InfoJobs and Adzuna are deferred until lawful accessible integration and actual user value are established. Do not broaden scope during closure.

## Current observed evidence
- Jobgether official API preview and 10-item metadata-only committed capture succeeded on the operator PC. The immediate second identical capture recognized 10 known identifiers, created zero duplicate CaptureItems; SQLite integrity was ok; zero Jobgether entries were promoted to Posting/SourceDocument.
- PRs #535–#545 added read-only preview, identity guards, local read-only audit, metadata observation staging, operator CLI, date sort, enriched metadata, advisory triage, CLI presentation and no-op repeat handling.
- Jobgether is **not** executable through the Discovery UI (source capability remains `execution_available=False`). Full verified description retrieval, explicit Spain work eligibility, safe promotion and real review round-trip remain unaccepted.
- #546 structural detail check is under CI and **does not** establish source provenance or remote eligibility.
- #499 proposes deleting contaminated *frozen review set membership rows on export*. Do not merge before preservation of human review history, application references, immutable import receipts and backup/recovery are explicitly audited. A reversible dry-run report is preferred.
- Open source extension PRs #524–#527 were closed without merging during closure triage; their code is not in `main`.

## Completion gates (all required for expanded source scope)
1. No P0/P1 regression in certified LinkedIn and Applications paths.
2. Jobgether's source detail is acquired with trustworthy provenance and structurally verified identity; ambiguous eligibility stays pending.
3. Discovery UI can execute a bounded Jobgether saved search and expose capture counts, quality warnings, failures and review-ready items.
4. Deduplication prevents double-review and never overwrites human decisions or applications.
5. One real Windows end-to-end multi-source session: search → capture → verified details → frozen AI work package → import → Review Inbox decision → application state → restart.
6. Backup/recovery and exact-head CI green, with up-to-date control files and no unresolved release blocker.

## Interaction budget
- Phase 0 PR triage/document baseline: 1–2 interactions.
- Phase 1 full source detail evidence: 3–5.
- Phase 2 Discovery/Review integration: 3–4.
- Phase 3 relevance/eligibility: 2–3.
- Phase 4 real acceptance: 2–3.
- Phase 5 freeze/documentation: 1–2.
Total planned: 12–19, risk-adjusted planning cap 20. Not a guarantee.

## Workflow rules
Group related code changes by accepted outcome; run Ruff and targeted unit tests before requesting expensive full CI; never present unverified source metadata as review-ready. Do not ask the operator to run routine tests reproducible in CI. Preserve existing application/human review state. Stop expanding features after acceptance criteria pass.
