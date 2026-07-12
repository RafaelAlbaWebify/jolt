# LinkedIn adapter foundation

This phase defines the source boundary without automating an authenticated LinkedIn account.

## Evidence-first capture sequence

1. Read visible listing cards.
2. Extract a durable source job ID and the listing evidence.
3. Select one listing.
4. Wait for the detail panel to expose the expected job ID.
5. Verify job ID, title, and company before accepting description text.
6. Reject stale or mismatched detail panels.
7. Preserve page number, visible IDs, pagination state, and warnings.

## Contracts

- `ListingCandidate`: evidence visible in a result card.
- `DetailEvidence`: detail-panel evidence plus identity verification.
- `PaginationEvidence`: page number, visible IDs, and next-control state.
- `CaptureRunEvidence`: grouped listings, details, page evidence, and warnings.
- `SourceAdapter`: source-neutral parsing interface.

## Test strategy

The repository includes a synthetic LinkedIn-like page. Unit tests validate parsing and stale-panel rejection. A Playwright browser test clicks a result and waits for the detail identity to change, proving that capture must rely on observed identity rather than a fixed sleep.

## Deliberately excluded

- Credentials or stored LinkedIn sessions in GitHub Actions.
- CAPTCHA, login, or access-control bypass.
- High-volume crawling.
- Live selectors being treated as stable without a supervised discovery run.
- Automatic application submission.

A later local supervised adapter may use a user-controlled persistent browser profile, bounded searches, rate limits, screenshots, and redacted diagnostic packs.
