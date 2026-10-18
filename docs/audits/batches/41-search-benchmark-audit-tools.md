# Batch 41 — Capture experiment integrity and hardline audits (4 tools)

Full-file source inspection against main `21461c90f057a8312e1250735c25888278a1617b`. No live experiment, database query or network call was performed.

| File | Finding |
|---|---|
| `tools/audit-indeed-persistence.py` | **TOOL-17 Medium:** read-only SQLite URI and source/artifact hash checks are sound in scope, but a JOIN to potentially multiple `capture_artifacts` rows can multiply capture-item rows; same key appears repeatedly and counts may be inflated. Verify uniqueness constraints before claiming. Expected ZIP `cards` keyed by source_job_id collapses duplicates. |
| `tools/analyze-indeed-search-benchmark.py` | **TOOL-18 Low:** prior pages' `listing_signals` are combined using `dict.update`, so later page signals overwrite earlier evidence for the same job ID. Purpose is coverage benchmarking, not eligibility assessment. Output report includes location snippets, but omits descriptions. |
| `tools/analyze-linkedin-search-experiment.py` | **TOOL-19 Medium:** uses ordinary `sqlite3.connect(db)` which can create a new empty database if wrong path supplied; subsequent queries then fail. Read-only URI would enforce nonmutation. Writes `search_experiment_analysis.json` directly to evidence directory; report may disclose search URLs and job IDs. Hard-coded experiment group labels are exploratory, not generic grouping. |
| `tools/audit-language-hardlines.py` | **TOOL-20 Medium:** explicit read-only SQLite and opt-in raw source text are positive. The default stdout report still exposes titles, companies, URLs and location; sharing requires review. Evaluates only latest AI review by posting; that behavior matches stated scope but not entire review history. |

**Architecture notes:** multiple tools separately decode captures, SQLite review state, timestamps and report JSON; actual helper extraction requires consumer compatibility tests. No proven safe deletions.

**Count:** +4 unique non-test files; 215/300 (71.67%) marked reviewed on this branch, 85 pending; 227/333 (68.17%) total including 12 frontend tests, 106 pending. Batch 40 separately proposes four further unique files, making 219/300 across both open PRs if both merge. These tags remain source review coverage, not runtime certification.