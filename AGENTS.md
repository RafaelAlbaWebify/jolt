# JOLT engineering execution contract

These rules apply to AI-assisted and human-assisted repository changes. They are part of the repository, not chat-only instructions.

## Outcome-first delivery
- Start with a complete, testable user-facing outcome and explicit acceptance criteria.
- Group related code, tests, launchers, documentation and fixes into **one functional delivery**. Do not open a PR per helper, script, or formatting correction.
- Avoid intermediate ZIPs, manual extraction, repeated check-in questions and progress claims based only on commits.
- Reuse current architecture, models, storage and launchers before adding new ones.
- Reserve human intervention for authenticated local-browser acceptance or genuinely unavailable resources. Provide a single copy-paste command when needed.
- Track **operationally certified outcomes** separately from commits, PRs and roadmap interactions. Never mark a phase complete from unit tests alone when real-world acceptance is required.

## Pre-PR quality gate
1. Work on a branch from current main.
2. Validate the **branch** using .github/workflows/ci.yml (push to development branches is supported).
3. Inspect all backend steps: Ruff lint, Ruff format, Pyright and pytest. Review frontend and Windows scripts when relevant.
4. Fix *all* reported failures in the same branch and rerun. A passing unit subset does not replace complete CI.
5. Open one PR only after the branch preflight is green. Merge only after required PR checks are green.
6. Do not claim a tool was run locally if it was not. GitHub Actions is the reproducible fallback when local tooling is missing.

## Safety and integrity
- Never promote an observed job to verified, Spain-eligible, Posting, Review or Application without explicit evidence and corresponding acceptance criteria.
- Persist only through established JOLT tables and transactions. Default to read-only or rollback; require explicit commit for new writes.
- Validate canonical source identity, provenance, bounded limits, and idempotent reruns.
- Preserve raw provenance or clearly state its absence; do not equate a JSON summary with a complete job description.

## Interaction budget
- Deliver coherent functional milestones in grouped implementations. Minimize user messages and repeated manual tests.
- Give concise status only on meaningful changes, blockers or verified results.
- Record unresolved limitations precisely; do not invent an ETA, approval, green CI or runtime success.
