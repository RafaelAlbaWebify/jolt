# Batch 28 — Frontend boot, readiness and history (5 components)

**Baseline:** main `a1481ee131f6305d20dd8ebf4a547a7904cdc906`. Five complete source files reviewed, no browser E2E executed.

| File | Detailed observation |
|---|---|
| `frontend/src/main.tsx` | **FE-01 Low maintenance:** imports many global style sheets into the root bootstrap, so cascade order can affect unrelated screens and all styles are bundled at entry. Componentized scoped styling could help after visual snapshot and build size profiling. Root missing guard is positive. No current functional blocker identified. |
| `frontend/src/test/setup.ts` | **No evident blocker:** single Testing Library Vitest matcher registration, with no runtime side effects. |
| `frontend/src/ApplicationOverviewAutoExpand.ts` | **FE-02 Medium:** global `MutationObserver` watching `document.documentElement` subtree on every child mutation and querying document may trigger substantial scans during large workspace updates. **FE-03 Medium:** synthetic summary `click()` changes disclosure state but is remembered per DOM element in WeakSet; on re-render/new element or when user re-collapses workflow, behavior can differ from deliberate user preference. No observer disconnect logic in module. |
| `frontend/src/ProfessionalExecutionReadiness.tsx` | **FE-04 Medium:** effect fetch lacks abort/ignore cleanup; switching `active` false or changing `apiBase` during an in-flight request can apply stale readiness response. **FE-05 Medium status:** heading displays `readiness.ready` but not `execution_available`; inspect backend status contract so Ready does not imply browser runtime proven. Positive error/loading states. |
| `frontend/src/ReadinessHistory.tsx` | **FE-06 Medium:** asynchronous history loads have no stale posting-id response guard; when a component instance is reused for another posting while a request is in flight, prior posting history may be shown. **FE-07 Low/Medium:** nested `refreshReadiness` calls `loadHistory`, and both mutate the same `loading` flag; settle/refresh sequence can obscure spinner/error sequencing. Human-initiated refresh is explicit; no automatic writes on mount. |

**Verification:** React Testing Library rerender/slow network tests for stale props, instrument mutation frequency for overview auto-expand, and test refresh errors. No behavior changed.

**Cumulative proposed coverage:** **172/333 = 51.65%**, 161 pending. Static review only.
