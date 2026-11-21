# JOLT Quality Gate — complexity and performance

This supplements, rather than replaces, the existing CI checks (Ruff, formatter,
Pyright, pytest, frontend tests/build, npm audit, and PowerShell parsing) and
the database-isolated `tools/local-quality-gate.ps1`.

## Local audit

From repository root:

```powershell
python tools/quality_complexity_gate.py --output "$HOME/Downloads/JOLT_QUALITY_METRICS.json"
python -m unittest discover -s tools -p test_quality_complexity_gate.py -v
```

The report inventories tracked production Python/TypeScript/PowerShell files,
flags files above 650 lines and Python functions above 100 lines as **debt
signals**, and records a deterministic-fixture JSON round-trip benchmark
(400 job-like records, median of 7 timings). This is **not** a browser/Indeed
benchmark or an end-to-end performance guarantee.

On pull requests CI also compares code growth against the merge-base of
the target branch. Growth greater than 150 net lines in any production source
file, or any new production source file above 650 lines, fails this additional
gate. This is a **review trigger**: reduce or modularize the change rather
than gaming the limits. Existing large files only generate a report and do
not block unrelated changes. Number of files is tracked but **not hard-capped**;
merging unrelated modules to reduce file count usually harms maintainability.

The output is uploaded as a CI artifact. Real performance regressions require
separate workload-specific baselines for JOLT capture, persistence, AI package
export and import; such measurements must be taken on a stable local fixture,
not live job-board websites.

## Safety

This tool does not access production databases, does not open Chrome,
does not invoke a capture, and does not rewrite application source.

## Follow-on work

1. Add regression tests for the shared capture-limit contract and pre-browser
   validation, using synthetic fixtures.
2. Profile real package generation and SQLite queries using anonymized local
   fixtures; add statistical budgets only after collecting baselines.
3. Track change in function complexity, duplication, source line count,
   dependency graph depth and test coverage over time.
4. Remove obsolete files only after proving no entrypoint imports them.
