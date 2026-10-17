# Batch 18 — LinkedIn and market preparation (preliminary)

These two modules have been read but their dependency tracing, tests, and impact verification remain incomplete. Do not mark them audited yet.

- `linkedin_command_center.py`: capture comparisons appear scoped to category rather than an individual profile or target; confirm intended semantics. Queries read all records before limiting display count. The analysis export loads referenced screenshots; confirm permissible evidence paths and operator privacy policy.
- `market_preparation_import.py`: a JSON read/parse error is treated like an empty history. Check whether subsequent import can replace historical entries after corruption. Locking is process-local and shared temporary filenames may conflict under multiple processes.

These are inspection leads only, not validated defects. Coverage remains 136/333 pending the complete audit.
