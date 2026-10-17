# Batch 32 — Discovery, extraction, portfolio and preferences styling (4 components)

Source baseline main `a1481ee131f6305d20dd8ebf4a547a7904cdc906`. Four complete CSS files read. CSS-only inspection does not constitute a visual regression test or runtime bug reproduction.

| File | Observation |
|---|---|
| `frontend/src/DiscoverySearchQueue.css` | **STYLE-01 Low:** uses fixed light-theme colors rather than shared design tokens; risks mismatch under dark/high-contrast presentations. Grid and mobile breakpoint are defined; no obvious functional blocker in this isolated stylesheet. |
| `frontend/src/ProfessionalStructuredExtraction.css` | **STYLE-02 Low:** term excerpts use 0.85rem muted color inside a narrow responsive grid, potentially reducing readability; visual contrast/accessibility needs a browser or computed-style test. Layout uses min-width:0 appropriately. |
| `frontend/src/LinkedInSearchPortfolio.css` | **STYLE-03 Low/Medium:** repeated literal colors/radii and several separate 760px mobile media sections indicate maintainability cost and cascade drift; consolidate only with screenshot comparison. Performance table has horizontal overflow, a positive safeguard. |
| `frontend/src/JobPreferences.css` | **No source-level blocker observed.** Fieldsets, labels, responsive one-column rule and checkbox sizing provided; test contrast and small-screen keyboard focus separately rather than inventing CSS defects. |

**Follow-up:** exercise actual light/dark, 320px viewport, zoom and keyboard focus; treat accessibility findings as unverified until measured.

**Cumulative proposed coverage:** 191/333 = 57.36%, 142 pending. All documentation-only.
