# Batch 38 — Developer tools, context generation and preflight (5 files)

Complete source review of five pending tools on 2026-10-18. Both context tools serve different output contracts; overlap is not proof either can be deleted. Windows scripts were not executed.

| File | Reviewed behavior and potential risk |
|---|---|
| `tools/ai_context_bundle.py` (242 lines) | Builds tracked/changed-source context and freshness manifests. TOOL-01 Medium: git() suppresses Git failures, potentially emitting unknown/default state. TOOL-02 Medium: budget skipping/early exit can omit relevant source; manifest accurately records skips/truncation. |
| `tools/build_ai_context.py` (168 lines) | Generates smaller deterministic state snapshot. TOOL-03 Medium: malformed PROJECT_STATE.json or TEST_STATUS.json raises without actionable recovery. Git status functionality overlaps bundle script, but contracts differ. |
| `tools/finish_ai_session.py` (67 lines) | Writes session handoff JSON and Markdown then rebuilds delta context. TOOL-04 Medium: writes are not atomic across output files; exception can leave inconsistent snapshots. Canonical-state reminder is positive. |
| `tools/dev-preflight.ps1` (100 lines) | Runs lint, format, Pyright, pytest, npm audit/test/build and reports outcomes. TOOL-05 Medium: full_pr_gate means flags meet full configuration, not that gates passed; downstream consumers must also require pass=true. Quick-mode warning is positive. |
| `tools/assert-jolt-runtime.ps1` (118 lines) | Fail-closed Windows x64, PowerShell, Git, uv, Node and npm version checks. TOOL-06 Low: hard-coded supported version bands need cross-check with installation/release manifest; no sensitive mutation observed. |

**Architecture overlap confirmed, not removable lines:** the two AI context scripts both read canonical state and Git branch/head/recent logs. Potential shared helpers, but no safe deletion claim without consumer mapping.

Unique non-test reviews added: 5. Cumulative non-test register **205/300 = 68.33%**, 95 pending; total register **217/333 = 65.17%**, 116 pending. Source review only, no Windows tests run.