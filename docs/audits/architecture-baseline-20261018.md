# JOLT architecture and audit inventory baseline — 2026-10-18

**Repository tree:** `9742f9a43cf47bc2f6da105c4109c819cfbb8d2f` (merged main, PR #609). GitHub recursive-tree API returned 773 entries / 750 blobs, `truncated=false`. Counts below are **measured from current Git tree**, unlike estimated percentages.

## Inventory and code bytes

| Category | Files | Bytes |
|---|---:|---:|
| `backend/src/jolt/**/*.py` | 165 | 1,413,239 |
| `frontend/src/**/*.{ts,tsx,css}` excluding `.test.` | 56 | 534,316 |
| direct `tools/*.{py,ps1,bat}` | 79 | 457,549 |
| **Production/code-and-tool inventory total** | **300** | **2,405,104** |
| Frontend `.test.` files in `frontend/src/` | 33 | 215,053 |

**Caveats:** byte totals are UTF-8 source blob sizes, **not line-of-code counts**, runtime footprint, compiled output, nor proof that a module is reachable. All files elsewhere, including backend tests, migrations, frontend configs and documentation, are excluded. The 300/333 register count is **consistent** with these exact path selectors and the additional 33 frontend test files; however this does not prove each register path still matches the tree without a full path-set reconciliation.

## Concentration among largest 10 production/code-tool files

| File | Bytes |
|---|---:|
| `backend/src/jolt/strategy_runtime.py` | 57,047 |
| `frontend/src/App.tsx` | 56,977 |
| `frontend/src/ProductionUXRefresh.css` | 54,868 |
| `frontend/src/ApplicationDashboard.tsx` | 49,721 |
| `backend/src/jolt/linkedin_capture.py` | 35,936 |
| `backend/src/jolt/main.py` | 32,297 |
| `backend/src/jolt/market_intelligence.py` | 32,070 |
| `backend/src/jolt/indeed_capture.py` | 32,062 |
| `frontend/src/LinkedInSearchPortfolio.tsx` | 27,612 |
| `backend/src/jolt/database.py` | 27,524 |

Top ten combined **406,114 bytes = 16.89%** of inventoried source bytes. This is a **triage heuristic**, not evidence of unnecessary code. A large source file can be justified.

## Architecture simplification audit plan (not yet completed)

1. **Reachability:** enumerate routes/CLI entries/UI imports, build direct dependency graph, detect zero-consumer modules; exclude imports used dynamically before calling code dead.
2. **Capability overlap:** compare LinkedIn capture flows, unified vs deprecated AI exchange routes, multiple preparation flows and UI variants; preserve data contracts and exports before deprecation.
3. **Duplication:** identify copy/paste logic (error handling, pagination, persistence, network polling, selectors) with actual matching function bodies, not file-name similarity.
4. **Complexity hotspots:** measure real LOC, function counts, cyclomatic complexity, coupling and test coverage on fixed `main` SHA. These figures are **not yet measured**.
5. **Safe reduction candidates:** rank by verified callers, deletion/migration risks, necessary backwards compatibility, effort and test evidence; **no deletion** until contract/usage analysis.
6. **Evidence standard:** distinguish `SOURCE_READ`, `DEPENDENCIES_TRACED`, `TESTS_CHECKED`, `RUNTIME_VERIFIED`, `REMOVAL_CANDIDATE` and `REMOVAL_VERIFIED`; use these as separate checkboxes, not one inflated `AUDITED` status.

## Baseline operational count

Register after batch 35: **191/300 non-test code/tool entries marked reviewed**, 109 pending, **12/33 test entries marked reviewed**, 21 pending. The marked entries have mixed verification depth; exact number meeting all strict audit criteria **unknown**. No source code removed, no demonstrated LOC reduction. The analysis above is quantitative inventory, not completion of the simplification phase.
