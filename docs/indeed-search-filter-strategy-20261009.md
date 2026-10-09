# Indeed search filters — 2026-10-09

The current JOLT preset searches supply only keywords, geographic location, recency (last seven days) and date ordering. They do **not** guarantee that Indeed has applied its Remote, salary, work type or other interactive filters.

## What is available in the Indeed Spain UI

Operator screenshot showed keyword and location inputs plus filter chips: Remoto, Fecha de publicación, Salario, Distancia, Método de solicitud, Tipo de empleo, Sector, Nivel de educación, Turno y horario. It also showed ordering by relevancia/fecha. A "Distancia 1" indicator means a distance filter is active, but the screenshot does not disclose the chosen radius. No unobserved filter values should be inferred.

Indeed's own guidance recommends varying keywords, regions/radius, and the Remote filter when available; remote does not imply eligibility to work from Spain. https://es.indeed.com/help/job-seekers/articles/115005875163-buscar-teletrabajo?co=ES&hl=es

## Immediate implementation

`tools/run-indeed-curated-search.ps1` now accepts:
- `-SearchUrl`: exact HTTPS Indeed `/jobs` URL copied *after* configuring the filters in Indeed's UI. This preserves portal-controlled query parameters and is preferred for filters whose current encoding JOLT has not verified.
- `-Days`: 1/3/7/14 day recency for fixed presets.
- `-Sort`: `date` or `relevance` (relevance leaves the sort parameter unset).
- `-RadiusKm`: optional local radius.

Examples:

```powershell
.\tools\run-indeed-curated-search.ps1 -Search support-local -Days 3 -Sort date -RadiusKm 25 -MaxJobs 30 -MaxPages 4
.\tools\run-indeed-curated-search.ps1 -SearchUrl 'https://es.indeed.com/jobs?q=soporte&l=Vigo&fromage=3' -MaxJobs 30 -MaxPages 4
```

## Pending optimization — do NOT claim complete

1. Compare multiple query strings and location scopes for local Vigo/remote Spain searches, tracking source IDs per preset, new vs known, and relevant vs rejected.
2. Identify/avoid known job IDs before detail enrichment using an efficient read-only identity lookup; preserve duplicate refresh policy and lineage when needed.
3. Consider local filters for recency, distance, and user-verified remote eligibility; never infer eligibility from keywords or remote badge.
4. Verify generated URL against actual Indeed UI behavior and server result ordering; absence of a parameter does not always prove site default.
5. Add cross-run capture effectiveness metrics and tests before marking search optimization accepted.

The existing 40-offer capture proves speed and multipage mechanics, **not relevance or search portfolio efficiency**.
