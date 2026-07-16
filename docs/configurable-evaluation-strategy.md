# Configurable evaluation strategy

## Purpose

JOLT evaluation must be configurable for any user while preserving an auditable distinction between:

- eligibility;
- current demonstrated fit;
- transferable fit;
- interview readiness;
- likely onboarding fit;
- opportunity quality;
- strategic career value;
- uncertainty.

A single score is retained only as a sorting aid. It must never conceal a hard blocker or imply that short-term study is equivalent to professional experience.

## Private profile location

The active profile is local and private by default:

```text
.jolt/profiles/active.private.json
```

The whole `.jolt/` directory is Git-ignored. A different file can be selected with `JOLT_PROFILE_PATH`.

Public source code, tests and documentation must use synthetic profiles. Real names, email addresses, CV text, certificates and personal preferences must not be committed.

## Evidence levels

| Level | Meaning |
|---:|---|
| 5 | Repeated professional ownership |
| 4 | Professional hands-on experience |
| 3 | Portfolio, homelab or substantial practical evidence |
| 2 | Structured training or certification |
| 1 | Awareness or stated interest |
| 0 | No supporting evidence |

Certifications can support level 2. They cannot independently establish production ownership, years of experience, management responsibility, developer seniority or administrator ownership.

## Interview-aware evaluation

The engine exposes three different fit values:

- `fit_now`: evidence available before preparation;
- `fit_by_interview`: realistic fit after the configured preparation window;
- `fit_on_the_job`: likely fit after normal onboarding.

Only these gap types can produce short-term interview uplift:

- `preparable_in_days`;
- `preparable_in_1_to_2_weeks`.

The following do not receive short-term uplift:

- `preparable_in_1_to_3_months`;
- `experience_gap`;
- `fundamental_mismatch`;
- `unknown`.

This allows JOLT to recommend a support role where product knowledge, SQL support scenarios or API troubleshooting can be prepared before a later technical interview, without pretending that a week of study creates years of professional software-development or platform-ownership experience.

## Recommendation values

- `strong_pursue`
- `pursue`
- `pursue_if_condition_met`
- `review_manually`
- `defer`
- `do_not_pursue`

Eligibility and excluded role families override numeric fit.

## Profile structure

```json
{
  "schema_version": 1,
  "profile_id": "local-job-search",
  "version": 1,
  "display_name": "Local JOLT user",
  "role_families": [],
  "capabilities": [],
  "eligibility_rules": [],
  "preparation": {
    "hours_per_week": 10,
    "default_days_until_technical": 10,
    "ai_guided_study": true,
    "documentation": true,
    "labs": false,
    "mock_interviews": true,
    "maximum_parallel_processes": 3
  },
  "weights": {
    "role_alignment": 20,
    "demonstrated_capability": 25,
    "transferable_capability": 10,
    "gap_feasibility": 15,
    "opportunity_quality": 15,
    "strategic_value": 15
  }
}
```

Weights must total exactly 100.

## Migration plan

This first slice introduces and tests the generic strategy contract without replacing historical evaluation or readiness records.

The next slice will:

1. load the active private profile at runtime;
2. persist its versioned configuration in `profile_versions`;
3. create new immutable evaluations under a new engine version;
4. derive readiness reports from the same strategy assessment;
5. preserve all existing `rafael-job-search:v2`, `profile-rules-v2` and `application-readiness-v1` evidence as historical records;
6. update API and UI projections without converting automated recommendations into human decisions;
7. keep analysis exports, audits, backups and certification compatible.
