# Batch 24 — Package entrypoints, professional capture plan, evidence root and deletion (5 components)

Baseline main `3caefe090dfe4b71ebd8eab16a2f2811ad6b5cd7`. Complete static reads of five source files. No runtime calls or user-data changes.

| Module | Evidence and findings |
|---|---|
| `backend/src/jolt/__init__.py` | One-line backend package docstring. **No evident blocker** within file. |
| `backend/src/jolt/sources/__init__.py` | One-line source-adapter package docstring. **No evident blocker** within file. |
| `backend/src/jolt/professional_intelligence_capture_plan.py` | **PI-08 Medium:** `execution_available` defaults True; builder does not probe browser/runtime or evidence root. Plan availability is a declarative configuration, not proof capture can run. Positive: disabled/out-of-scope sources excluded, safety constraints explicit. |
| `backend/src/jolt/professional_intelligence_evidence_root.py` | **PI-09 Medium:** `get_professional_evidence_root` calls `ensure_default_professional_evidence_root` and can mkdir/commit from a nominal GET/readiness path; impacts read-only diagnostics and test isolation. **PI-10 Medium:** `configure_professional_evidence_root` accepts any writable directory without an explicit owned-root policy; investigate existing artifacts on root replacement and backup semantics. Positive: resolved containment check and concurrent singleton provision retries. |
| `backend/src/jolt/professional_intelligence_capture_deletion.py` | **PI-11 High recoverability:** deletes artifact/run database rows and commits before `shutil.rmtree`; filesystem failure can orphan files with no durable run index. **PI-12 Medium:** deleting a run checks `running` before calling `get_professional_capture_run` to update expiry state; confirm transition semantics and concurrent worker guard. Positive: confirmation phrase, containment, running-run restriction. Test only with disposable file/DB fixtures. |

**Cumulative proposed source coverage:** **157/333 = 47.15%**, 176 pending. Source-reviewed does not mean tested/fixed.
