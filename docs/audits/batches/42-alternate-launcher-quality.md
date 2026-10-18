# Batch 42 — Alternate shutdown, restore and quality gates

Read four complete pending tools on 2026-10-18, against `6e3249745862f63a2434c505b3c297c7c6f6395d`. Findings are source-based, not proof of runtime exploit.

- `tools/jolt-stop.ps1` (52 lines): **HIGH** unconditional `Stop-Process -Id` for owner of ports 8000/5173; no repo identity or service command validation. Potential shutdown of unrelated local services. Distinct from `stop-jolt.ps1`, whose defensive work is in separate PR #616. Prefer retiring unsafe alias only after tracing all callers and preserving operator behavior.
- `tools/preflight-jolt.ps1` (41 lines): **MEDIUM** overlaps `dev-preflight.ps1` yet `-FullTests` omits frontend test execution and npm audit. Not equivalent to complete gate; different defaults can confuse operators.
- `tools/local-quality-gate.ps1` (104 lines): **MEDIUM** clears database URL and substitutes a temporary profile before running backend gates, then hashes active DB before/after. Hash equality guards one path but tests could use another DB if config resolves differently; user profile isolation is not comprehensive DB isolation. Records summary only on success.
- `tools/restore-jolt.ps1` (34 lines): **HIGH** `uv ... backup verify` and `restore` did not check `$LASTEXITCODE`, so failures may be mislabeled successful. Fix proposed separately in PR #620. Active database target protection is positive.

Architecture simplification opportunity: two stop entrypoints with unequal safety guarantees, and overlapping preflight scripts. No proven safe deletion yet; trace callers and validate windows workflows.

Four unique non-test source reads: relative to `main` 219/300 marked reviewed (81 pending), 231/333 rows including tests (102 pending). Separate PR #619 proposes four additional non-test reads, giving 223/300 only after both are merged and register reconciled.