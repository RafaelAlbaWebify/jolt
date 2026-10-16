# Normalized job offer contract (Phase 1.2A / 1.2B)

The current JOLT sources are **LinkedIn, Indeed, InfoJobs and Jobgether**.
Adzuna is disabled/removed from the active discovery catalog and editor. Existing
legacy saved searches and captures, if present, are not deleted.

## Boundaries

- Each portal keeps its own transport, login handling, extraction, pagination and raw evidence.
- `sources/normalized_offer.py` defines a common **intermediate hand-off format**,
  with conversion from the existing capture payloads.
- This phase does **not** change capture ingestion, migrations or the existing
  `Posting` schema. No existing database rows are rewritten.
- Source ID, URL, title and company are mandatory. Description, location,
  salary, work mode, contract, experience, languages and publication timestamp
  may be absent. Unknown work mode must remain `unknown`, not "remote".
- The original capture metadata remains attached and can support source-specific
  improvement. Verification flags only reflect evidence supported by the capture.
- `observed_at` is distinct from `published_at`. The earliest observation and
  latest re-observation will be handled by provenance work in Phase 1.4.
- An offer appearing on multiple portals may represent the same underlying
  vacancy. **No automatic cross-portal merge occurs in this phase.** Durable
  linking and safeguards belong to Phase 1.3 / 1.4.
- A Posting is not an AI endorsement, an application or proof that remote
  work from Spain is permitted.

## Compatibility checks (Phase 1.2B)

`backend/tests/test_normalized_offer.py` covers:
LinkedIn and Indeed live capture shapes; InfoJobs bounded, hash-checked detail
capture; Jobgether structured offer identity and detail; absent optional
values; source identity mismatches; and unverified evidence.

The test suite uses representative fixture payloads, not live network calls.
Earlier live InfoJobs and Jobgether acceptance validates their capture paths,
but this change has not itself been exercised against live portals.

## Remaining phases

1.3: durable source-local and cross-source deduplication decisions.
1.4: multiple source observations and per-source history linked to a Posting.
1.5: display sources in Review Inbox and analytical groupings.
1.6: integrated end-to-end and migration/regression acceptance.
