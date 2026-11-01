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

## AI review package and import integrity
- Treat `GET /api/ai-work-package/review-export` as an external-AI handoff. Its `classification_authority: external_ai` and `advisory_only` preanalysis are not JOLT's final native classification. Audit native classification only from persisted evaluator outputs; never use imported ChatGPT labels as JOLT labels.
- Use the supported unified import route, `POST /api/ai-work-package/import`, and validate against the current `UnifiedAIUpdate`, `AIReviewBundleImportRequest`, and `AIReviewImportRequest` models. The update envelope requires `reviewed_at` and `review_version`; the review bundle and capture groups must retain their exact contracts and IDs. The Review Inbox UI must call the read-only `POST /api/ai-work-package/preflight` first and proceed to import only when membership and deterministic source gates pass.
- In review contract 1.2, both `mandatory_requirements` and `mandatory_requirement_results` are lists of structured requirement objects. Never serialize `mandatory_requirements` as a list of strings.
- Before delivery, call the read-only review preflight endpoint. It must check exact posting/capture membership, unique IDs, field types/enums, aliases, dates, and deterministic gates; report all capture-level failures together before import. Stage 1 `REJECT`/`MANUAL_REVIEW` stops fit scoring; positive decisions require eligible geography, clear language/clearance, and verified official work-from-Spain evidence when LinkedIn labels the role remote.
- Never falsify evidence or silently alter a decision just to pass validation. Re-evaluate a contradiction; keep unresolved eligibility conditional and report any changed decisions explicitly.
- Render FastAPI validation details whether `detail` is a string or an array of objects. Show each error's path and message; do not coerce the array to `[object Object]`.

## Interaction budget
- Deliver coherent functional milestones in grouped implementations. Minimize user messages and repeated manual tests.
- Give concise status only on meaningful changes, blockers or verified results.
- Record unresolved limitations precisely; do not invent an ETA, approval, green CI or runtime success.

## Independent human job decisions

Apply and Reject must remain available for each pending posting from any capture source, including manual intake, before AI review. Persist an explicit human decision without fabricating AI reviews, scores, or verified eligibility. Validate any supplied AI/native evaluation IDs against the posting; absent IDs are allowed. Pursue opens the existing application preparation workflow, without submitting externally. A decision affects only the selected posting; other capture jobs remain pending. AI import must continue to preserve human decisions and its own evidence requirements.
