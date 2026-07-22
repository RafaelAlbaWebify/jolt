# Commercial application workflow redesign

The current application workflow must be replaced with a pipeline-first product model.

## Primary workspace

Applications should use a board with these user stages:

- Preparing
- Applied
- Interviewing
- Offer
- Closed

The opportunity inspector remains focused on fit analysis and a single action: move to preparation.

## Application card

Each application card should show role, company, current stage, last activity, next action, due date, and document state.

Opening a card should expose:

- Overview
- Tasks
- Interviews
- Contacts
- Documents
- Timeline

## Structured records required

- submitted_at
- next_action
- next_action_at
- employer_reference
- contact records
- interview records
- task records
- document references

## UX constraints

Do not embed the complete application lifecycle in the opportunity inspector. Do not use large explanatory buttons as stage controls. Use concise stage actions and a visible pipeline.
