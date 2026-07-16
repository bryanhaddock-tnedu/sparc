# SPARC Retrospective - 2026-07-16 12:17

## Retrospective Metadata

- Date: 2026-07-16
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Forecast Review Queue logic and interface review
- Participants: Bryan Haddock, Florie, and Codex acting as SPARC engineering partner
- Branch: `develop`
- Prior stage baseline: `77cf572`
- Handoff target: Bryan, Florie, and future SPARC Codex sessions

## Stakeholder Request

Florie reported that the Forecast Review Queue was confusing and needed review. The review covered the displayed terminology, the relationship between page filters and decision scope, the apply/dismiss lifecycle, and the backend mutation path.

## Findings

1. The queue is intentionally full-fiscal-year because the decision service recalculates Forecast and mapped Roadmap Actual totals for the complete selected fiscal year. It ignored the billing filters above, but the UI did not explain that boundary clearly.
2. `Suggested Add` is the positive difference between mapped Roadmap Actual hours and canonical Product + Bucket Forecast hours. Applying it adds that delta to one explicit Team Member + Fiscal Month Forecast line; it does not change Actual entries.
3. Rejecting a recommendation recorded history but left the identical recommendation in the active queue, allowing the same evidence snapshot to be rejected repeatedly.
4. Apply and reject actions had no final confirmation describing their data impact.
5. The backend recalculated the recommendation at submission but did not verify that the result still matched the totals shown to the reviewer. A sync or Forecast edit between page load and submission could therefore apply a different delta than the reviewer saw.

## Delivered Behavior

- Renamed the surface from `Forecast Review Queue` to `Forecast Adjustment Review`.
- Explains that the queue uses full-year Product + Bucket totals and is not affected by the billing filters above it.
- Uses explicit column and summary labels: Current Forecast, Mapped Actual, Add to Forecast, Forecast Owner, Forecast Month, Pending, and Proposed Add.
- Labels Team Member choices with labor Role and adds accessible labels to each decision control.
- Replaced ambiguous `Apply` and `Reject` commands with `Add Hours` and `Dismiss`.
- Added confirmation text showing Product, Bucket, Team Member, Fiscal Month, current full-year Forecast, proposed full-year Forecast, mapped Actual, and the fact that Actual hours do not change.
- A dismissed recommendation leaves Forecast and Actual untouched, leaves an immutable decision record, and removes only the identical current snapshot from pending work.
- A dismissed recommendation returns when Forecast, mapped Roadmap Actual, recommendation kind, or proposed delta changes.
- Recent Decisions now distinguishes Forecast-added decisions from dismissed decisions and shows the prior Forecast, mapped Actual, and proposed delta snapshot.
- The API requires the reviewed Forecast and Roadmap Actual totals and rejects stale decisions before any write.
- Applying to an inactive Team Member is now rejected server-side.
- Bumped root release version to `0.1.60` and frontend/interface version to `0.1.97`.

## Data And Ownership Guardrails

- Forecast remains canonical at Product + Team Member + Bucket + Fiscal Month/Fiscal Year.
- Actual remains Jira/worklog-owned and read-only through this workflow.
- Roadmap Actual is evidence used to propose a controlled Forecast adjustment; it does not overwrite Forecast automatically.
- Dismissal is a decision about one evidence snapshot, not deletion and not a permanent Product/Bucket exclusion.
- The workflow remains Admin-only through the Jira/Rovo integration router authorization dependency.
- No schema migration was introduced.

## Verification

- Targeted Forecast recommendation service tests: 2 passed.
- Complete backend suite in Docker: 115 passed.
- Frontend TypeScript and Vite production build in Docker: passed.
- Stale-snapshot test confirms no Forecast or decision row is written when reviewed totals no longer match.
- `git diff --check`: passed.
- Existing Vite bundle-size warning remains non-blocking and unrelated.

## Stage Acceptance Steps

1. Sign in as an Admin, open Admin, then Jira, and locate Forecast Adjustment Review.
2. Confirm the copy identifies the review as full-year and independent of the billing filters above.
3. For one pending row, select a Forecast Owner and Forecast Month, then choose Add Hours.
4. Verify the confirmation states the exact delta, destination, current Forecast, proposed Forecast, mapped Actual, and that Actual will not change.
5. Confirm the action, verify the row leaves Pending, and verify Recent Decisions shows Forecast added with the reviewed snapshot and target.
6. Dismiss another pending row and verify it leaves Pending, appears as Dismissed, and changes no Forecast or Actual hours.
7. Verify a dismissed recommendation returns only after its full-year evidence changes.

## Remaining Work

- Florie stage acceptance of this revised queue remains open.
- The next stakeholder item is the Team page Product Forecast review.

## Collaboration And Handoff

Bryan expects a UI review to include the underlying entity and mutation logic, not only visual cleanup. When a review exposes a real integrity or lifecycle flaw, fix it within the milestone, verify it, document it, and continue without asking him to re-specify established guardrails. Keep testable changes independently deployed to stage whenever practical.
