# JOLT change-impact analysis

Run from the repository root:

```powershell
python tools/change_impact.py --base HEAD --output "$env:TEMP\jolt-change-impact.json"
```

Use `--changed backend/src/jolt/schemas.py` to inspect a planned edit before changing files. `--strict-contracts` exits nonzero if capture contracts are inconsistent or unresolvable.

The command is read-only except for its optional JSON report. It includes changes not staged, staged, and untracked. Reports show reverse Python/TS imports, literal frontend HTTP paths matched to backend routes, direct SQLite model references and explicitly unresolved boundaries.

This is **static evidence**, not proof of runtime behavior. Dynamic route registration, interpolated API calls, SQL query semantics, PowerShell invocation parameters and filesystem side effects still need integration testing. `test_candidates` are possible regression tests, not evidence that they have run.

CI runs the analyzer for all PRs and retains a JSON artifact. It rejects confirmed capture contract mismatches when both producer and receiver limits are available in the checkout. Local-only `capture-limits.json` is not present in remote main at this baseline; an `unknown` status is not a pass and must be reconciled before certifying limits.

Never discard or overwrite the operator's uncommitted capture changes, backups, ZIPs or database while reconciling a branch.
