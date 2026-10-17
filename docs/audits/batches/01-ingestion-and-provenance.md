# Batch 01 — shared ingestion, source evidence and identity (7 components)

**Source inspected:** GitHub `main` commit `27ecd6944c9cf2216cbaa6bf8884dd126c7d9f29` on 2026-10-17. Reviewed full source of the seven files below, including their conditions, side effects and boundary calls; cross-checked earlier user-uploaded `JOLT_SOURCE_AUDIT.zip` for historical comparison. This is a **static source audit**: there was no authenticated browser execution or production database mutation. Earlier source audit `JOLT_CAPTURE_INGEST_AUDIT.md` provides more broad capture pipeline context but is not proof these seven modules are defect-free.

**Counted:** 7 / 333 production components = 2.10%. All seven are `AUDITED-ISSUES` because at least one unresolved correctness, evidence or integration concern remains. Findings below are either **CONFIRMED FROM CODE**, **RISK/NEEDS TEST**, or **RESOLVED IN MAIN**. An issue is not considered resolved merely by opening a PR or finding a test.

## 01. `backend/src/jolt/capture_ingestion.py` (136 lines)

- 22–39: creates a new immutable `SourceDocument` from raw text and its SHA-256; calls `flush`, not `commit` (transaction owned by caller). Confirmed behavior.
- 41–44: normalized source URL (or content-hash mode) builds identity key; existing Posting lookup by identity key only. Cross-portal semantic matches are not automatically merged here; source registry imposes an additional constraint.
- **SH-01 HIGH — confirmed**, 46–72: on confirmed identity duplicate, fields `canonical_url`, `title`, `company`, `location`, `description` are overwritten unconditionally and a new evaluation added. No source freshness/completeness comparison is visible before refresh. Existing human decisions are not explicitly changed here, but display quality can regress. **Needed**: guard refresh on evidence quality/freshness while preserving original provenance and human decisions; disposable SQLite regression.
- 91–119: creates Posting and Evaluation for new identity. Each accepted import triggers evaluation; do not mislabel it as a human-approved AI review.
- **Status:** AUDITED-ISSUES; leave production code unchanged until behavior/compatibility decision is documented.

## 02. `backend/src/jolt/supervised_source_promotion.py` (167 lines)

- 28–36: validates stored artifact integrity with SHA-256 and parses JSON; malformed or altered evidence is rejected.
- 37–57 InfoJobs: checks supported artifact type, offer identity, canonical URL and isolated description SHA; delegates body extraction to `inspect_offer`.
- 58–73 Jobgether: demands canonical `/offer/` source identity and non-mismatched `extracted_unverified` JSON payload.
- 75–88: requires nonempty title/employer, description >=150 characters, HTTPS and consistency with previously staged item. This 150-char rule is a **business heuristic**, not proof of authenticity.
- 91–114: only known source and supported capture mode, no already linked item, and `observed_unverified` status may promote; checks attached artifact.
- **SH-04 MEDIUM — confirmed**, 120–150: invokes shared `ingest_capture_item`, then **sets `posting.description = description` again**. Because the ingestion parser may reformat input, this changes the normalized result and could overwrite a higher-quality previously ingested duplicate without comparing evidence. Test deterministic repeat-capture refresh.
- 136–161: registers portal identity and artifact-linked portal observation before caller commits, records warning that Spain remote eligibility is not verified. Transaction ownership stays with caller.
- **Status:** AUDITED-ISSUES.

## 03. `backend/src/jolt/infojobs_observations.py` (209 lines)

- 22–39: only canonical detail URL with ID, extracted status, entire body SHA-256 integrity and heading/text agreement pass inspection.
- **IJ-02 HIGH — confirmed**, 40–57: exact line delimiters `Descripción` and `Categoría` required, company inferred from first header line, location from punctuation. A valid alternate InfoJobs layout is structurally rejected, which is different from genuinely absent detail. Needs structural site-specific extraction with strictly bounded fallback and fixtures from a real page.
- 70–82: source, mode, source search URL and bounded number of offers validated. **IJ-01 RESOLVED IN MAIN:** route now calls shared `_listing_identity(search_url)`, accepting the user's `/ofertas-trabajo?keyword=...` form; validated in PR #597.
- **IJ-04 HIGH — confirmed**, 86–105: if **any** previous CaptureItem with same source job ID exists, no new evidence is staged. Previously unresolved/unpromoted items cannot receive fresh richer evidence in this function. This can make repeated attempts unable to recover incomplete old captures. Requires explicit idempotent source-observation/retry policy preserving history.
- 107–177: creates CaptureRun/Page/Item and hash-backed artifact for novel IDs only; stores `observed_unverified`, not automatic approval; no commit.
- 180–205 CLI: commit only on explicit `--commit`, otherwise rollback. Observe that `stage_report` returning no novel records is a nonexceptional result.
- **Status:** AUDITED-ISSUES.

## 04. `backend/src/jolt/infojobs_operational_run.py` (141 lines)

- 22–34: makes SQLite backup with `sqlite3.backup` before committed operator import; rejects non-SQLite configured backend.
- 37–56: stages report and joins CaptureItem with CaptureRun to locate source IDs. **IJ-03 PARTIAL FIX MERGED:** PR #598 chooses current run or already-imported evidence over arbitrary prior record; however no explicit deterministic query ordering, unique constraint validation, or stale-unpromoted refresh strategy is established. Status is *mitigated, not fully closed*.
- 57–94: promotes each selected item, checks Review Inbox presence and review status, distinguishes newly imported from previously imported; does not claim Spain eligibility/AI approval.
- 97–141: all-or-nothing `commit`/rollback, optional JSON report, SQLite backup only when `--commit`.
- **Status:** AUDITED-ISSUES; add repeated-capture fixtures with old unpromoted and new verified evidence.

## 05. `backend/src/jolt/jobgether_operational_run.py` (128 lines)

- 23–53: accepts source-specific `extracted_unverified` detail only with canonical Jobgether ID, title/employer, description >=150, no mismatches and no repeated ID; skips incomplete records. Note: accepted subset selection must be reflected truthfully in reporting.
- **JG-04 MEDIUM — needs test**, 56–80: staging accepted subset then querying *all historical* items; prefers current capture run or previously imported item but lacks stable ordering of candidates. Verify treatment of multiple old rows and whether correct artifact is promoted.
- 81–90: verifies posting presence in Review Inbox; stores `work_from_spain_verified=False` and no AI review performed.
- 93–123: backup first when committing, rollback on exception; `--commit` gate prevents accidental persistence.
- **Status:** AUDITED-ISSUES.

## 06. `backend/src/jolt/jobgether_structured_offer.py` (143 lines)

- 18–36: HTMLParser flattens structured description markup to plain text.
- 39–55: recursively discovers JSON-LD `JobPosting` objects in arrays or `@graph`.
- 74–97: validates canonical offer URL and parses structured blocks, but **JG-02 HIGH — confirmed**: if the number of discovered JobPosting records is not **exactly one**, returns unresolved. Even genuine visible details without JSON-LD cannot pass this extractor.
- 98–118: extracts title/employer/description; checks visible heading and structured URL identity against canonical URL. No full visible-page detail fallback.
- 119–142: extracts applicant-location claims as metadata; `spain_declared` is not proof of employment eligibility and is kept separate from `work_from_spain_verified=False`.
- **Status:** AUDITED-ISSUES. Capture a privacy-safe real detail fixture before broadening extraction, to prevent importing generic page/sidebar text.

## 07. `backend/src/jolt/sources/source_identity_registry.py` (74 lines)

- 18–31: only `identity_verified` offers and existing Posting/SourceDocument references may register a source identity.
- 32–48: if portal/source ID already exists, reassignment to a different Posting raises rather than silently changing association. Maintains `last_seen_at` and source metadata on matching Posting.
- **SH-05 MEDIUM — needs test**, 38–48: repeated capture against the same portal ID but a *different* Posting identity key (e.g. changed URL query/description) raises a conflict; confirm transaction rollback and ensure the UI reports a resolvable source conflict instead of losing capture evidence.
- 50–63: inserts portal identity for a new portal ID; separate cross-site duplicates are not automatically united here.
- **Status:** AUDITED-ISSUES.

## Cross-cutting conclusions / decisions before modifying production

1. **Tailor capture per portal; standardize evidence after extraction.** Do not transfer LinkedIn selectors to InfoJobs/Jobgether. Adapt source-specific HTML only in corresponding collectors.
2. **No blind overwrite** of existing accepted descriptions. Require a tested quality/freshness rule and preserve human decisions and first-seen provenance.
3. **Repeat-observation recovery:** fresh valid InfoJobs detail must be promotable even after a prior unpromoted observation; do not merely pick any historical CaptureItem.
4. **Visible-detail Jobgether fallback:** only after capturing an actual canonical source identity plus verified heading, employer and detail-body provenance.
5. Treat **review coverage 7/333** independently of operational certification (currently not established for InfoJobs/Jobgether).

**Next batch (02):** seven upstream collectors and executors: `linkedin_discovery_batch.py`, `linkedin_capture.py`, `live_capture_workflow.py`, `indeed_chrome_attach.py`, `indeed_capture.py`, `indeed_live_capture.py`, `discovery_execution.py`. Estimate **7 additional components**, reaching 14/333 = 4.20% *only when examined and documented*. Read full modules and their relevant tests; do not pre-credit them.
