# Batch 40 — Sensitive data, workspace audits, launchers and daily workflow (4 unique files)

Read the full sources of the following four pending tools from main `21461c90f057a8312e1250735c25888278a1617b`. `tools/ai_context_bundle.py` was also re-read for dependency context but was previously audited and **is not counted again**.

| File | Source-level finding |
|---|---|
| `tools/audit-jolt-sensitive-data.ps1` | **PRIV-01 Medium:** checks required gitignore rules by simple textual membership and reports paths/counts, but does not verify Git's actual ignore precedence, tracked secrets or archive contents. The `passed` flag must not be presented as a comprehensive sensitive-data security certification. Local directory inventories are intentionally read-only. |
| `tools/audit-workspace-navigation.ps1` | **TOOL-15 Medium:** invokes `start-jolt.ps1` and then unconditionally invokes `stop-jolt.ps1` in `finally`; it could disrupt an operator's pre-existing JOLT session rather than only processes created by this invocation. Validates expected JSON and three screenshots, but not their semantic correctness. |
| `tools/validate-windows-launchers.ps1` | **TEST-14 Medium:** static string checks on three launchers confirm presence of certain commands, but not that launcher runs or migration/backup contracts work. Literal search is sensitive to harmless formatting changes and may miss unsafe execution order. Appropriate as smoke contract, not runtime certification. |
| `tools/jolt-daily-workflow-audit.py` | **TOOL-16 High operational:** test generates a real manually ingested posting, auto Pursue review, application, task, interview and outcome against `127.0.0.1:8000`; no temporary database isolation, cleanup or explicit operator confirmation in this script. Running this audit on production user data can leave persistent synthetic opportunities and applications. Several HTTP responses and browser errors can be recorded in full summary; treat output as sensitive. Screen captures use known static viewport and browser closures; browser failure before explicit close may rely on context manager cleanup. |

**Simplification:** workspace audit, daily workflow audit and launcher validation have distinct assurance levels despite similar names. Do not consolidate without preserving meaningful acceptance gates. Source findings were **not reproduced at runtime**.

**Counts:** four unique files were newly read: non-test entries `215/300 = 71.67%` (85 pending); all rows `227/333 = 68.17%` (106 pending). These remain coverage tags, not proof of end-to-end audited dependencies.
