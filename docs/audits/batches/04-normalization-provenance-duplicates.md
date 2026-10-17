# Batch 04 — normalized offers, provenance and duplicate association (6 components)

**Source baseline** `3e90b5f241ef176a86f26887c70cebb08890aa00`. Static full-file source review with cross-reference to `capture_ingestion`, `supervised_source_promotion` and Review Inbox. Tests not directly run in this audit. Never infer that a match is safe for automatic merge/apply.

| Component | Source-level behavior | Findings / proof needed |
|---|---|---|
| `backend/src/jolt/sources/normalized_offer.py` (147 lines) | 18–64 Pydantic common `NormalizedJobOffer`; 65–147 source-specific `normalize_captured_offer` dispatch with trusted URL, typed portal ID, description and verification flags | **NM-01 Medium (design gap)**: common schema already exists, but the four portal runners do not all call this normalized interface **before** staging, and original browser-specific raw payloads remain separate. Standardization is partly implemented, not a new framework to invent. Regression: four portals same accepted fields/rejection reasons. |
| `backend/src/jolt/sources/portal_observations.py` (96 lines) | 24–87 verified CaptureItem+artifact digest check, links source identity, deduplicates capture event; 88–96 listing | **PR-01 Medium (risk)**: record is allowed only after identity was registered and `CaptureItem.detail_status='verified'`. Failed/partial observations remain in captures/artifacts but not visible as verified portal observations; avoid misleading a zero-observation chart as zero capture attempts. Check duplicate hash and same-run reentry. |
| `backend/src/jolt/sources/confirmed_duplicates.py` (128 lines) | 19–31 request/response; 32–127 checks both postings, verified identities and evidence similarity, creates explicit `ConfirmedDuplicateLink` | **DD-01 Low (correct safeguard)**: no automatic destructive merge based on title alone. Confirm both directions and repeat confirmation are idempotent; human decision and original source documents should remain separately addressable. |
| `backend/src/jolt/sources/cross_portal_candidates.py` (114 lines) | 18–30 candidate model; 31–114 compares postings and registered source identities, returns probable cross-portal duplicates | **DD-02 Medium (risk)**: candidate generation is bounded; semantic assessment quality depends on normalized location/employer and job-description evidence, and may miss legitimate same-company multilingual duplicates. False negatives are acceptable if no automatic merge; make source visibility explicit. |
| `backend/src/jolt/sources/duplicate_assessment.py` (65 lines) | 22–65 normalization and evidence-based duplicate assessment; distinct vs needs review vs confirmed conditions | **DD-03 Low (sound boundary)**: exact employer/title/location/description requirements protect against false positive merges. Quantify false negatives on portal-specific examples without weakening the confirmation safety. |
| `backend/src/jolt/capture_artifacts.py` (46 lines) | 13–25 persistent artifact model; 27–46 staging with SHA-256 hash over raw payload and flush in same session | **PR-02 Medium (risk)**: sha verifies raw artifact integrity, not authenticity of a web page or accuracy of text extraction. Keep original source URL/detail identity linked to capture; avoid replacing artifact on recapture. **No-commit** within helper is appropriate. |

### Cross-batch implications
1. Existing `NormalizedJobOffer` and source registry provide the standardization target; no parallel schema is justified without demonstrated incompatibility.
2. Duplicate handling is **not** the same as evidence normalization: probable cross-portal duplicates remain distinct until safely confirmed.
3. Ingestion state must separate **captured**, **structurally valid**, **registered**, **shown for review**, **reviewed**, and **eligible in Spain**. No portal should report a later state as an earlier one.
4. Audit classifications are static findings/risk hypotheses, not evidence of broken production behavior. Severity requires prioritization in change phase.

### Coverage
This closes **batch 04** (6 files). Combined coverage batches 01–04: **28 / 333 = 8.41%** source-reviewed, **305 outstanding**. Related tests and migrations require separate inventory; operational status is unrelated to this number.

**Next:** batches 05+ should examine complete application-facing search configuration, discovery API, saved-search persistence, AI Review Inbox, frontend and Windows entrypoints. Do not upgrade PENDING files to AUDITED merely by filename, grep or CI.
