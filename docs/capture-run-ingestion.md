# Capture-run persistence and ingestion

JOLT persists source capture activity separately from canonical job opportunities.

A capture run records the source, mode, search URL, warnings, timestamps, observed pages, visible source job IDs, and one capture item per listing. A capture item may link to a source document and canonical posting only after its detail identity has been verified.

Fixture capture follows this boundary:

1. Parse listing candidates and pagination evidence.
2. Parse the detail supplied for each source job ID.
3. Verify job ID, title, and company against the selected listing.
4. Persist rejected detail evidence when verification fails.
5. Send verified details through the existing canonical intake, duplicate detection, and evaluation workflow.
6. Link the capture item to the resulting source document and posting.

Repeated captures retain new source evidence while canonical URL duplicate detection prevents duplicate opportunities. Authenticated live capture remains deliberately outside this phase.
