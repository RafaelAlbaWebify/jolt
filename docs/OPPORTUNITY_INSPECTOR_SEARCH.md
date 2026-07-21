# Opportunity search and inspector slice

This slice continues issue #54 after the compact Opportunities queue redesign.

## User-visible behavior

- Search matches opportunity title, company, and location.
- Sorting supports highest score, lowest score, title A-Z, and company A-Z.
- Query changes reset pagination to page 1.
- Inspect opens one focused right-side dialog without expanding the queue.
- The inspector preserves automated review, application readiness, readiness history, source and preparation links, and application workflow actions.
- Escape closes the inspector.
- The Close button receives initial focus.
- Background scrolling is locked while the inspector is open.
- Focus returns to the triggering Inspect button after close.

## Automated certification

Run on Windows:

```powershell
& "C:\Users\ralba\Documents\GitHub\jolt\tools\audit-opportunity-experience.ps1"
```

The generated `JOLT_OPPORTUNITY_EXPERIENCE_<timestamp>.zip` contains:

- `01-default-queue.png`
- `02-search-results.png`
- `03-title-sort.png`
- `04-opportunity-inspector.png`
- `opportunity-experience-audit.json`

The audit validates populated search counts, title sorting, horizontal overflow, inspector dimensions, important links, automated review visibility, initial Close-button focus, Escape dismissal, and browser page errors.

## Populated evidence

The Windows audit `JOLT_OPPORTUNITY_EXPERIENCE_20260721_095913` passed on 141 opportunities:

- no horizontal overflow at 1440x1000;
- search expected and displayed 3 matching rows;
- title sort placed `2nd Line Support` first as expected;
- inspector measured 680x1000;
- source and preparation-pack links were visible;
- automated review was visible;
- Close received initial focus;
- Escape closed the inspector;
- no browser page errors or audit findings.

## Boundary

No backend API contract, evaluation rule, capture behavior, or application data model is changed by this slice.
