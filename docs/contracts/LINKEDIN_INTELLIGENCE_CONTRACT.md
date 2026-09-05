# LinkedIn Intelligence Module Contract

## Responsibility
Capture and present candidate/profile/network/activity evidence and exchange that evidence with ChatGPT without confusing partial capture with absence.

## Inputs
Supervised LinkedIn profile/section/network pages, user-approved capture actions, imported AI recommendations/status updates.

## Outputs
Profile/network/activity evidence with provenance and capture quality metadata; command-center views; AI analysis/recommendation exchange state.

## Guarantees
- login/authwall/checkpoint/empty captures are excluded from candidate evidence and retained only for audit/quality diagnostics;
- partial/bounded network capture is explicitly labeled and missing contacts are never treated as absent;
- profile evidence is separate from job capture evidence;
- AI feedback remains derived/user-reviewable and does not rewrite source captures.

## Dependencies
Visible Chromium/Playwright, local persistence/evidence store, unified AI exchange layer.

## Failure behavior
Safety/auth failures stop capture and expose quality/status; stale AI analysis should be visible rather than silently treated as current.

## Non-responsibilities
Job-source capture, application lifecycle, autonomous LinkedIn messaging or connection actions.