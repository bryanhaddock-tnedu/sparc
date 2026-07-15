# SPARC Retrospective - 2026-07-15 09:46

## Retrospective Metadata

- Date: 2026-07-15
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Ambiguous Roadmap gap candidate visibility
- Participants: Bryan Haddock, Florie, and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, and future SPARC Codex agents

## Stakeholder Request

Florie reviewed the remaining Roadmap Actual Gaps after the Jira hierarchy fixes reduced the queue from roughly 21 rows to 8. She asked for ambiguous tickets to show only the Roadmap Items that actually compete for that ticket instead of presenting every fiscal-year Roadmap Item in the selection list.

The status logic remains deterministic:

- `mapped` means exactly one valid Roadmap Item association exists for the ticket in the selected fiscal year.
- `ambiguous` means two or more valid Roadmap Item associations exist.
- `unmapped` means no valid association exists.
- A gap is any Actual attribution row that is not mapped.

## Implementation

- The Roadmap Actual API now returns mapping candidates keyed by Jira ticket.
- Each candidate contains the Roadmap Item ID, Jira key, and title.
- Candidates are attached per ticket rather than per grouped Actual row because one grouped row can contain multiple Jira tickets with different candidate sets.
- An ambiguous gap dropdown now contains only that ticket's competing Roadmap Items.
- The ambiguous prompt now says `Choose competing Roadmap Item`.
- A truly unmapped ticket still receives the complete fiscal-year Roadmap Item list so an admin can establish a manual mapping.
- Mapped Product, Team Member, Bucket, Actual hours, and cost behavior is unchanged.

## Guardrails

- This change does not alter Jira hierarchy discovery or automatically choose among competing Roadmap Items.
- Forecast and Actual persistence are unchanged.
- Roadmap Item candidates are attribution context only and do not affect Program Area authorization.
- Correcting conflicting Jira relationships remains the durable source-data fix. A manual ticket mapping resolves the current stored ambiguity, but Jira can reintroduce a competing relationship on a later Roadmap sync while the source hierarchy remains ambiguous.

## Verification

- Full backend suite: 109 tests passed.
- The Roadmap attribution regression test now proves that a mapped ticket returns one candidate and an ambiguous ticket returns the exact two competing Roadmap Items.
- Frontend production build: passed.
- `git diff --check`: passed.
- Existing Vite large-chunk warning remains and was not introduced by this milestone.

## Versioning

- Root package version: `0.1.54`.
- Frontend/interface version: `0.1.91`.
- Version identifiers remain short because overlong identifiers previously broke stage deployment.

## Stage Validation

1. Sign in as Admin and open Admin > Jira Sync.
2. Locate a Roadmap Actual Gap with status `AMBIGUOUS`.
3. Open its Roadmap Item selector.
4. Confirm the selector lists only the Roadmap Items linked to that Jira ticket.
5. Confirm an `UNMAPPED` row still offers the complete fiscal-year Roadmap Item list.
6. Select one competing item and confirm the gap reloads as mapped.

## Collaboration Notes

- Bryan expects completed, testable milestones to be documented, committed, and pushed to `develop` so GitHub triggers stage deployment.
- Retrospectives are required handoff material for future Codex tasks.
- Stage remains the stakeholder validation environment; Docker is appropriate for engineering regression testing.
