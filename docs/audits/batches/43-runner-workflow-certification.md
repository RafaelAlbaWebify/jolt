# Batch 43 — audit launchers and full-cycle orchestration (5 unique files)

Five files read completely at commit `6e3249745862f63a2434c505b3c297c7c6f6395d`. Static source inspection, no local Windows runs.

| File | Findings |
|---|---|
| `tools/run-jolt-workflow-audit.ps1` | Runs HTTP health checks then Python workflow auditor; tests exit status. Creates timestamped ZIP; audit mode labelled read-only, but actual side effects depend on target Python. No snapshot privacy sanitizer. |
| `tools/run-jolt-work-items-audit.ps1` | Explicitly discloses persistent task/interview fixture creation on the selected application. **High operational hazard:** no database isolation or guard to block user data contamination. |
| `tools/run-jolt-stage-reversal-audit.ps1` | Discloses creating persistent local application fixture, without enforcing disposable database. Capture review required before sharing output ZIP. |
| `tools/run-jolt-live-ui-audit.ps1` | **High false-success:** native `uv run python` exit code unchecked before ZIP and success message; fix proposed in PR #623. |
| `tools/run-full-cycle-certification.ps1` | Uses temporary `JOLT_DATABASE_URL` and reports cert output, but **High:** `taskkill /PID /T /F` uses PIDs loaded from files with no executable identity verification. If reused, could terminate unrelated processes. **Medium:** caller's `JOLT_DATABASE_URL` and `JOLT_CERT_*` environment variables are overwritten in process without restoring previous values; processes launched at fixed ports 8000 and 5173 without preflight owner identity. |

**Architecture:** five launcher wrappers have repeated backend/frontend readiness and archive packaging. Preserve different fixture semantics and prove caller contracts before consolidation. **Count:** +5 non-test reviews relative to merged batch 40 = 220/300 (73.33%), 80 pending. Other independent branch PRs #619 and #621 hold 8 further unique reviews, so union if all merge is 228/300; this file alone does not claim 228 merged.
