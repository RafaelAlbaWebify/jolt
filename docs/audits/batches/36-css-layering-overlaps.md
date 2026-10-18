# Batch 36 — CSS layering and verified selector overlap

Baseline `main` `10f2dbfc1bb3dfe5eebeb7f50ded3506058fca4a`. Six complete CSS files fetched and analyzed by selector; source-level audit and overlap measurement. CSS fixes require browser visual, keyboard and accessibility regression testing before merging.

| Source | Lines | Bytes | Main issue / verification |
|---|---:|---:|---|
| `frontend/src/ApplicationPipelineBoard.css` | 246 | 14,123 | Defines application workspace, board, modal overlays and lane scrolling; `.application-workspace` also defined in `ApplicationWorkspace.css`. Test effective scroll/height when importing both. |
| `frontend/src/ApplicationWorkItems.css` | 21 | 1,983 | Dense one-line CSS rule style makes diff review harder; distinct task/list classes and mobile grid. No confirmed functional defect. |
| `frontend/src/ApplicationWorkspace.css` | 316 | 5,229 | Reuses `.application-workspace` with different grid/spacing; later imported stylesheet may override. Styles for preparation forms and workflow partially overlap board assumptions. |
| `frontend/src/CompactInspectorOverrides.css` | 191 | 3,233 | Overrides `.opportunity-inspector`, `.inspector-header`, sticky actions, compact detail. Media query for height and width creates layout branches. |
| `frontend/src/CompactOpportunityWorkspace.css` | 298 | 4,926 | Base inspector width `min(680px,94vw)`, later overridden by both compact and workflow layers. Also defines `.inspector-backdrop` alignment. |
| `frontend/src/WorkflowRefinement.css` | 132 | 2,208 | Changes inspector to centered modal and width `min(1320px, calc(100vw - 72px))`, replacing side-drawer behavior. Explicitly redefines layout for inspector/backdrop and compact grid. |

## Reproducible selector-overlap evidence

Repeated selectors across distinct files in this six-file set include `.application-workspace`, `.opportunity-inspector`, `.inspector-header`, `.inspector-header h2`, `.inspector-sticky-actions`, `.compact-detail-grid`, `.compact-detail-grid .automated-review`, `.compact-detail-grid .dimension-grid`, `.compact-detail-grid .review-evidence-grid`, and `.inspector-backdrop`. These are **10 distinct selectors defined in 2–3 inspected files**, not 10 proven unused or duplicated implementations.

**Simplification hypothesis:** a consolidated component-specific inspector style contract could replace serial overrides. Actual removable CSS line counts **unknown**, because different viewport layouts and import order may rely on overrides. Keep until Playwright visual snapshots at desktop/mobile and modal/focus checks verify replacement.

**Coverage:** six unique non-test register entries reviewed. Non-test **197/300 = 65.67%** (103 pending); legacy all-row **209/333 = 62.76%** (124 pending). No production changes and no claimed LOC reduction.
