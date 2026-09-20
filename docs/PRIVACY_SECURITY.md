# Privacy and security review

Date: 2026-09-20

Scope: JOLT's local evidence store, authenticated LinkedIn browser profiles, generated exports, AI exchange files, and acceptance/recovery artifacts.

## Security model

JOLT is a local-first, single-user Windows application. It binds its backend and frontend to loopback interfaces during the supported startup flow. It does not provide multi-user authentication, remote tenancy, or encrypted application-level storage.

Production use therefore assumes:
- one trusted Windows user account;
- Windows device encryption/BitLocker where available;
- normal Windows account lock and sign-in protection;
- the JOLT repository and generated artifacts are not placed in broadly shared or public folders.

## Sensitive data inventory

| Location / artifact | Sensitivity | Contents / risk | Current control |
|---|---|---|---|
| `backend/data/jolt.db` | High | job evidence, review decisions, applications, notes, outcomes, market observations | local SQLite; excluded from Git |
| `.jolt/browser-profile/` | Critical | authenticated LinkedIn browser state, cookies/session material | local only; excluded from Git |
| `backend/data/playwright/linkedin-command-center/` | Critical | authenticated LinkedIn command-center browser state | local only; excluded from Git |
| `Downloads/JOLT_LINKEDIN_CAPTURE_*.json/.zip` | High | source text, job evidence and possibly screenshots | explicit export; not automatically uploaded |
| `Downloads/JOLT_LINKEDIN_CAPTURES/` | High | LinkedIn profile/connection capture evidence | explicit local capture output |
| `JOLT_AI_WORK_PACKAGE.json` and legacy AI review exports | High | selected JOLT context and evidence for external reasoning | explicit user export/import workflow |
| `Downloads/JOLT_ACCEPTANCE/` | High | backup/restore rehearsal artifacts including database backups | explicit operator acceptance output |
| browser localStorage import receipt | Low | imported file name, timestamp and imported-section names | browser-local metadata only |

## Findings

### 1. Browser profile is authentication material — HIGH
The persistent Playwright profile can contain cookies or other session state sufficient to act as the signed-in LinkedIn user. JOLT does not store the LinkedIn password itself, but the browser profile must be handled like a credential.

Controls:
- both profile roots are inside Git-ignored paths;
- profiles are not included in JOLT capture ZIP/JSON exports;
- profiles remain on the local machine unless the user copies them.

Operator requirement:
- do not sync, share, email or commit these directories;
- delete the profile if the workstation is transferred to another person or the JOLT installation is retired.

### 2. SQLite database is unencrypted at application level — ACCEPTED LOCAL RISK
The primary database contains personal job-search history and may contain free-text notes. JOLT does not encrypt SQLite itself.

Controls:
- database resides in `backend/data/`, which is Git-ignored;
- supported production use is single-user and loopback-only;
- backup/restore tooling preserves integrity but does not add encryption.

Operator requirement:
- use Windows device encryption/BitLocker for data-at-rest protection;
- do not place the repository on a shared network drive or public/synced folder unless that storage is independently protected.

### 3. Generated exports are plaintext — HIGH
Capture JSON/ZIP files, AI work packages, review exports and acceptance backups are portable by design and therefore leave JOLT's local storage boundary.

Controls:
- generation is an explicit user/operator action;
- files are written locally;
- no automatic cloud upload is performed by JOLT.

Operator requirement:
- treat generated exports as confidential;
- upload only the specific artifact intentionally chosen for analysis;
- remove stale exports from Downloads when no longer required;
- do not send acceptance backups or browser profiles to external services.

### 4. AI exchange requires explicit disclosure boundary — ACCEPTED WITH OPERATOR CONTROL
The AI work-package workflow intentionally exports selected JOLT evidence for analysis in ChatGPT. This is not an invisible background transfer.

Controls:
- export is user initiated;
- import is schema validated before JOLT applies returned intelligence;
- human-owned decisions remain authoritative.

Operator requirement:
- review the exported file before sharing it outside the local machine when sensitive context matters;
- never include browser-profile directories or raw database backups in the AI workflow.

### 5. Git leakage controls — PASS
Repository ignore rules exclude:
- `.jolt/`
- `data/`
- `backend/data/`
- generated artifacts directories

These rules cover the primary persistent database and browser-profile locations identified in this review.

## Residual risks

The following are accepted for the current local-first single-user production boundary:
- no application-level encryption of SQLite;
- no encrypted export container;
- no automatic retention/purge of files in Downloads;
- browser-session data is protected by filesystem/device security rather than a JOLT-specific secret store.

These would become release blockers if JOLT becomes multi-user, network-exposed, cloud-hosted, or centrally managed.

## Operator audit

Run:

```powershell
.\tools\audit-jolt-sensitive-data.ps1
```

The command is read-only. It reports whether sensitive storage locations exist, their approximate file counts/sizes, and whether the required Git-ignore rules are present. It does not inspect file contents and never deletes data.

## Review conclusion

For the documented local-first, single-user, loopback-only Windows deployment model, the identified privacy/security risks are understood and bounded provided the operator follows the handling requirements above and the workstation uses normal OS-level disk/account protection.

This review does not certify a SaaS, shared-machine, remote-access, or multi-user deployment.
