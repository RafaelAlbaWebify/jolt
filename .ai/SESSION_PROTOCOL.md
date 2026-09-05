# JOLT AI Session Protocol

Repository + `.ai/` are authoritative project memory. Chat is a temporary work session.

## Session start
1. Read `.ai/CONTEXT.md`.
2. Read `.ai/PROJECT_STATE.json`.
3. Read `.ai/KNOWN_ISSUES.md`.
4. Read `.ai/OPERABILITY.md`.
5. Read `.ai/ROADMAP.md` when prioritization/milestone work is involved.
6. Inspect Git status, current branch and commit; compare them with `PROJECT_STATE.json`.
7. If runtime behavior matters, inspect runtime identity and confirm the running backend actually corresponds to the checked-out code.
8. Read `PROJECT_MEMORY.md` for durable ownership/product constraints.
9. Load only the source/tests/docs relevant to the requested module.
10. Verify assumptions against current source/test/runtime evidence before modifying behavior.

## Source priority when facts disagree
1. directly verified runtime/test evidence;
2. current source code;
3. current configuration/data;
4. canonical `.ai/` and authoritative project documentation;
5. older/d dated documentation;
6. chat history;
7. assumptions.

Record discrepancies; do not silently harmonize them.

## During work
- Keep changes bounded to the active objective.
- Preserve module contracts and durable ownership rules.
- Do not redesign an established workflow merely to make a feature easier.
- Add/update regression tests for every deterministic bug or cross-workflow regression.
- Use temporary databases/test fixtures; do not mutate production/local user data during development.
- Treat source evidence as immutable input and AI output as derived/user-reviewable state.
- Missing evidence means uncertainty, not absence.
- Never inflate study/lab/project/certification into production experience.
- For job review, enforce source evidence -> Stage 1 hardlines -> candidate evidence -> fit -> recommendation.
- Do not compute fit after REJECT/MANUAL_REVIEW.
- Verify runtime behavior where the change is user-visible or integration-sensitive.
- Do not weaken CI/Playwright certification simply to pass.
- Use draft/open PRs for incomplete work; merge only exact expected head after all required gates are green.

## Completion claims
A change is **implemented** when code exists.
A change is **verified** only when relevant automated/runtime evidence passes on the applicable commit.
A roadmap item is COMPLETE only when its acceptance criteria and required evidence pass.
A readiness flag may become true only when the gate in `.ai/OPERABILITY.md` passes completely.
Never say `real prospect ready` unless that gate is fully satisfied.

## Session end
Before ending a development session, update canonical state where applicable:
- `.ai/PROJECT_STATE.json` — date, branch/commit, milestone, percentages/readiness, blockers, next actions, latest evidence.
- `.ai/TEST_STATUS.json` — exact suites/commit/results actually run.
- `.ai/KNOWN_ISSUES.md` — new/resolved/reclassified issues.
- `.ai/ROADMAP.md` — only if status/evidence changed.
- `.ai/DECISIONS.md` — durable new product/architecture decision.
- `.ai/REJECTED_APPROACHES.md` — abandoned approach worth preventing later repetition.
- `.ai/OPERABILITY.md` — only when readiness evidence changed.
- module `CONTRACT.md` — if public/module guarantees changed.

Record what changed, what was verified, what remains, current commit, active PR(s), and next recommended action.

## PR/merge discipline
Required gates for behavior changes:
1. CI
2. Playwright acceptance
3. Full-cycle Playwright certification

All must be green for the exact PR head unless a narrowly documented workflow legitimately does not trigger one of them. Never infer green status from an older head.

## Fresh-chat bootstrap test
A new chat should be able to answer from repository evidence:
- what JOLT is and who it is for;
- implemented vs broken vs unverified functionality;
- current milestone and blockers;
- recent completed work;
- next actions;
- architectural invariants;
- rejected approaches;
- objective operability/readiness;
- tests supporting each claim.

If answering any of those still requires old chat history, update `.ai/` before closing the session.