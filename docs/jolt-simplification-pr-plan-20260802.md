# JOLT Simplification PR Plan — 2026-08-02

This plan follows the product audit and current workflow map. It deliberately avoids a broad rewrite.

## Gate 0 — Repository hygiene

Before implementation:

- Close superseded open PRs after confirming no unique unmerged behavior remains.
- Do not merge the old stacked cleanup chain.
- Preserve `main` as the only implementation baseline.

## PR 1 — Clarify product boundaries

### Goal

Make the visible application match the proven user workflows without deleting backend data or endpoints.

### Changes

- Rename `Capture & Evidence` to `Capture Jobs`.
- Keep `LinkedInJobCaptureLauncher` as the primary content.
- Remove the configured-source capture controls, Professional run ledger, Professional evidence-root editor and Professional source editor from the Capture Jobs page.
- Rename `LinkedIn Command Center` to `LinkedIn Profile`.
- Add concise explanatory copy:
  - Capture Jobs discovers and evaluates vacancies.
  - LinkedIn Profile captures and improves professional presence.
- Move normal capture batch history from global Data Tools into Capture Jobs.
- Move reviewed decisions from global Data Tools into Review Inbox history.
- Keep backend Professional endpoints untouched for now.

### Acceptance

- A first-time user can tell where to capture jobs and where to analyse their LinkedIn profile.
- No profile source controls appear on the job capture screen.
- Existing job capture, review, applications and market data continue working.

## PR 2 — Consolidate profile source ownership

### Goal

Use one persisted source registry inside LinkedIn Profile.

### Changes

- Reuse the persisted Professional source registry as the authoritative registry.
- Render it inside LinkedIn Profile.
- Add explicit source selection and simple presets:
  - Profile essentials
  - Profile + activity
  - Full approved profile scope
  - Retry failed
  - Custom
- Remove browser-local target persistence from LinkedIn Command Center.
- Remove career/job sources from the default LinkedIn Profile capture presets.
- Keep deferred network/feed sources disabled.

### Acceptance

- The selected sources are visible before capture.
- The immutable run snapshot contains exactly the selected source IDs.
- There is no `maximum sources` selection ambiguity.

## PR 3 — Consolidate profile capture engine

### Goal

One browser/evidence implementation for LinkedIn profile capture.

### Changes

- Route LinkedIn Profile capture through the Professional run/artifact engine because it already has explicit authorization, bounded execution, contained evidence, SHA-256 manifests, integrity review and deterministic extraction.
- Migrate the useful Command Center evidence dashboard to read from that engine or a stable adapter.
- Preserve existing recommendation records and statuses.
- Remove Command Center Playwright capture endpoints and local target registry only after frontend migration and tests.
- Do not import profile-capture content into Review Inbox.

### Acceptance

- One browser profile/session boundary.
- One evidence root.
- One source registry.
- One capture ledger.
- Profile evidence and recommendations remain available.

## PR 4 — Simplify review decisions and history

### Goal

Every decision has a distinct next action.

### Changes

- Audit live counts for `consider`, `defer`, `needs_more_information`, `reject` and `pursue`.
- Keep only decisions with distinct behavior.
- Add Review History within Review Inbox.
- Default blocked/do-not-pursue roles to a collapsed blocked section or separate filter.
- Preserve append-only decision history.

### Acceptance

- Choosing a decision makes the next state obvious.
- No reviewed decision disappears without a visible destination/history.

## PR 5 — Simplify application actions

### Goal

Make the board answer: what must I do next?

### Changes

- Keep five board lanes.
- Make next action and due date primary.
- Confirm whether `Pursue` should create the preparation record immediately.
- Hide or defer empty contacts/documents/interviews tabs until relevant.
- Prevent board drag actions from inventing unsupported real-world events.

### Acceptance

- Every active card has one clear next action.
- Archive remains a visibility state, not a lane.

## PR 6 — Simplify Market Insights and Settings

### Goal

Keep only analysis that changes decisions.

### Changes

- Move full job-search preferences editor to Settings & Data.
- Keep preferences summary in Market Insights.
- Evaluate usage/value of market preparation export/import and LinkedIn recommendation ZIP loops.
- Remove browser-side ZIP parsing and file-backed imports if they duplicate direct in-app outputs.
- Keep target scope as default and all-role scope as secondary.

### Acceptance

- Market Insights shows current market evidence, blockers, gaps and strategy without workflow administration.
- Settings owns configuration and data-management operations.

## PR 7 — Remove unreachable and duplicate backend code

### Goal

Delete only after consumers are migrated and storage dependencies are verified.

### Changes

- Inventory frontend calls against backend endpoints.
- Remove endpoints with no remaining consumer and no required external contract.
- Remove duplicate capture services, registries and adapters.
- Preserve historical database tables when deletion/migration risk outweighs benefit; stop writing to them instead.
- Add a migration only when necessary for correctness, not cosmetic cleanup.

### Acceptance

- Full backend/frontend tests green.
- Windows job capture acceptance green.
- Windows LinkedIn profile capture acceptance green.
- Existing application and market records remain intact.
