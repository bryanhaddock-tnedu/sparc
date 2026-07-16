# SPARC Retrospective - 2026-07-16 12:06

## Retrospective Metadata

- Date: 2026-07-16
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Safe removal of accidentally added Product Forecast lines
- Participants: Bryan Haddock, Florie, and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, and future SPARC Codex sessions

## Stakeholder Request

Florie needs to remove an employee from a bucket on Product Detail when that forecast row was added accidentally. The investigation established that the row is not a separate bucket-roster entity: `Add Forecast Line` creates a zero-hour `ForecastEntry` at Product + Team Member + Bucket + Fiscal Month, while `ProductTeamMember` remains the Product-level roster assignment.

The implementation therefore removes only an empty Forecast line for the selected fiscal year. It does not remove the Team Member from the Product Team and does not alter Actual labor.

## Delivered Behavior

- Added a backend service and authenticated write API for deleting zero-value Forecast placeholders for one Product + Team Member + Bucket + fiscal year.
- Rejects removal when any month has positive Forecast hours.
- Rejects removal when any Actual labor exists in the same Product + Team Member + Bucket + fiscal year context.
- Preserves `ProductTeamMember`, including its active status.
- Added a trash icon beside editable Product Forecast rows.
- Enables the action only when displayed Forecast and Actual totals are zero and the row has no unsaved Forecast drafts.
- Confirms the exact Team Member, bucket, and fiscal year before removal.
- Reports success or failure inside the Forecast Lines control without replacing the Product page.
- Documented the data guardrail in the product brief.
- Added Florie's remaining Forecast Review Queue and Team Product Forecast reviews to the living backlog.
- Bumped root release version to `0.1.59` and frontend/interface version to `0.1.96`.

## Architectural Decision

No bucket-roster table or new relationship was introduced. Canonical Forecast grain remains Product + Team Member + Bucket + Fiscal Month/Fiscal Year. Product Team membership remains Product-level. Actual entries remain sync-owned and immutable through this workflow.

This keeps the change aligned with the existing model and gives `Add Forecast Line` a safe inverse without deleting legitimate planning or labor history.

## Verification

- Targeted removal tests: 2 passed.
- Complete backend suite in Docker: 115 passed.
- Frontend TypeScript and Vite production build in Docker: passed.
- `git diff --check`: passed.
- No database migration is required.
- Existing Vite bundle-size warning remains non-blocking and is unrelated to this change.

## Stage Acceptance Steps

1. Sign in as an Admin and open a Product page for the selected fiscal year.
2. Add a Product Team member to a bucket through Forecast Lines without entering hours.
3. Use the trash icon beside that Team Member in the bucket table and confirm removal.
4. Verify the bucket row disappears while the Team Member remains in Product Team.
5. Verify a row with positive Forecast hours or Actual hours does not offer an enabled removal action.

## Remaining Stakeholder Backlog

1. Review and simplify the Forecast Review Queue UI.
2. Review Team pages, especially the Product Forecast section, for correct ownership, calculations, terminology, and workflow.

## Collaboration And Handoff

Bryan wants stakeholder requests translated into the existing entity model before implementation, with no speculative schema additions. Once a change is testable, the expected workflow is to update living documentation, write a retrospective, commit, push `develop`, and verify the deployed stage SHA. Continue through the backlog without interrupting the flow unless a real blocker or data-integrity risk appears.
