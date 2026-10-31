# JOLT saved search portfolio — 2026-10-31

This portfolio replaces the previous 17 Indeed and 20 LinkedIn search set with 12 searches per portal. It is designed to keep local discovery separate from Spain-wide and international remote discovery.

## LinkedIn searches

| Scope | Searches |
|---|---|
| Greater Pontevedra, all work modes | IT support; auxiliar administrativo |
| Spain, remote | IT support; application support; Microsoft 365 support; IT operations; MES/ERP support |
| European Union, remote | Technical support engineer; application support engineer; Microsoft 365/Intune support |
| United Kingdom, remote | Technical support engineer |
| Worldwide, remote | Application support engineer |

These searches use the configured locations `90009802` (Greater Pontevedra), `105646813` (Spain), `91000000` (European Union), `101165590` (United Kingdom), and `92000000` (Worldwide). LinkedIn's date filter is past 30 days, sorted newest first. The remote work-type filter is applied to every non-local scope.

## Indeed searches

| Scope | Searches |
|---|---|
| Vigo, 30 km | IT support; auxiliar administrativo |
| Spain, remote listings | Technical Support Engineer; Application Support; Microsoft 365/Intune support; IT Operations Analyst; MES/ERP Support |
| United Kingdom, remote listings | Technical Support Engineer; Application Support |
| Ireland, remote listings | Technical Support Engineer |
| Indeed.com, remote listings | Technical Support Engineer; Application Support Engineer |

Indeed queries use the market-specific site and the portal's Remote location filter for remote searches. The general Indeed.com searches are a broad discovery lane; the review must verify country eligibility in the full posting.

## Capture and review

- Each saved search requests up to 100 jobs over at most 10 pages, matching the certified per-search capture contract.
- The location and remote filters control discovery only. They do not prove that an employer accepts work from Spain. The full-description review must assess that, along with qualifications and other hard requirements.
- Deduplicate postings across search URLs before review or application.
- The maximum configured exposure is 2,400 raw postings if all 24 searches reach their limits. Run selected groups first; a full AI review of all captured postings could use substantial model quota.

## Applying the portfolio

The saved searches are persisted in JOLT's local database, so restarting the application alone does not replace them. After merging, restart JOLT and run this from the repository root while its local API is available:

```powershell
python .\tools\sync-definitive-job-searches.py --apply
```

The script first backs up both current catalogs. It deletes superseded Indeed searches and disables superseded LinkedIn searches to preserve their history. Without `--apply`, it only prints the plan.
