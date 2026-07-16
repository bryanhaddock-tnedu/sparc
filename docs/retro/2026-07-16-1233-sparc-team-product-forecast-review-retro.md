# SPARC Team Product Forecast Review Retrospective

## Session

- Date: 2026-07-16
- Project: SPARC - Staff Planning and Resource Control
- Milestone: Team Product Forecast ownership, actuals, editing, and line management review
- Participants: Bryan Haddock, Florie, and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, and future SPARC Codex agents

## Stakeholder Request

Florie asked for the Team pages, especially the Product Forecast section, to be reviewed. This followed two independently completed requests: safe removal of accidentally added empty Forecast lines on Product pages and clarification of the Forecast Adjustment Review. Florie's July 16 acceptance of the most recent Roadmap/Billing checklist item applies only to mapped-ticket correction and remapping; it does not yet constitute acceptance of this Team Product Forecast milestone.

## Findings

- Team planner Actual totals were derived from Roadmap-attributed labor for the Product and could include labor from Team Members outside the selected Team.
- Team planner Program Area labels used Roadmap metadata instead of the SPARC-owned Product Program Area in `Product.office`.
- A Roadmap Item `source_team` value could make a Product appear in a Team planner even when the Team had no canonical Product, Forecast, or Actual relationship.
- The Team planner API serialized Team Members with bill rates for Leadership View Only users.
- The Team-specific Forecast write service treated a partial request as a full-year replacement and could zero untouched months. The interface happened to bypass that service, leaving unsafe behavior behind the API.
- Invalid planner text could be converted to zero instead of being rejected.
- Existing Forecast history for inactive Team Members and Products could disappear instead of remaining visible and read-only.
- Adding a second Product/Bucket Forecast line from Team Member Detail could overwrite the curated Product Team Member default Bucket.
- Team Member Detail did not offer the same guarded removal of an accidentally added empty Forecast line as Product Detail.

## Decisions And Guardrails

- Forecast remains one canonical SPARC record at Product + Team Member + Bucket + Fiscal Month/Fiscal Year regardless of which interface edits it.
- Team Actual totals come from canonical `ActualEntry` records for Team Members currently assigned to the selected Team. Roadmap attribution is not required for those totals.
- `Product.office` is the Program Area displayed in Team planning and remains the authorization boundary.
- Roadmap source-team and schedule fields are context only. They cannot independently create Product ownership or change Forecast grain.
- Partial Forecast saves update only submitted cells and cannot clear omitted months.
- Inactive Team Members and Products remain visible when they have history, but are read-only for new Forecast edits.
- Leadership View Only can see Team planning hours and dollars but cannot retrieve bill rates.
- Removing a Forecast line is allowed only when every Forecast month is zero and no Actual labor exists. Product Team membership remains intact.

## Implementation

- Rebuilt Team planner Actual aggregation around Team-scoped canonical Actual entries and preserved ticket/worklog evidence counts.
- Limited Team Product contexts to canonical Team membership, Forecast, or Actual evidence; Roadmap source-team metadata no longer grants ownership.
- Switched Team planner Program Area output to Product Program Area and added active Product state to the API contract.
- Applied capability-aware Team Member serialization so Leadership responses redact bill rates.
- Routed Team planner autosave through its dedicated partial-update API and changed that service to update submitted months only.
- Added explicit invalid-input feedback and prevented invalid values from being written as zero.
- Kept historical inactive Team Members and Products visible and disabled their Forecast inputs.
- Limited new Team Member Product Forecast selections to active Products and active Team Members.
- Preserved an existing Product Team Member default Bucket when another Forecast Bucket is added.
- Added guarded empty-line removal to Team Member Detail with the same backend rules used by Product Detail.
- Bumped the root release version to `0.1.61` and the frontend/interface version to `0.1.98`.

## Verification

- Full backend suite: 119 tests passed.
- Frontend TypeScript and Vite production build: passed.
- `git diff --check`: passed.
- New regression coverage proves Team-scoped Actual totals, unique ticket/worklog counts, Product Program Area output, Roadmap source-team non-ownership, partial Forecast updates, inactive-Product rejection, and Leadership bill-rate redaction.
- No database migration was required.
- The production build retains the existing Vite large-bundle advisory; it is not a build failure and is outside this milestone.

## Stage Acceptance Checklist

1. Sign in as Admin, open a Team, and enter Team Analytics > Product Forecast.
2. Confirm Team Actual totals include Actual labor for members of the selected Team and exclude another Team's labor on the same Product.
3. Confirm each Program Area matches the Product's Program Area in Product Settings.
4. Change one Forecast month, wait for the save confirmation, refresh, and confirm untouched months remain unchanged.
5. Enter invalid text in a Forecast cell and confirm the cell reports an error without saving zero; correct it and confirm autosave succeeds.
6. Confirm inactive Team Members or Products with historical Forecast data remain visible but cannot receive new edits.
7. Sign in as Leadership View Only and confirm Team planning remains visible while bill rates are absent.
8. On Team Member Detail, add a second Bucket Forecast line for an existing Product and confirm the Product Team default Bucket does not change.
9. Add and remove a zero-hour Forecast line and confirm Product Team membership remains. Confirm a line with Forecast or Actual hours cannot be removed.

## Handoff Notes

- Florie's accepted Roadmap/Billing item is documented separately in `docs/roadmap-billing-milestones.md` and commit `d45e9f9`; do not conflate it with Team Product Forecast acceptance.
- The Team page remains a labor planning surface, not a Roadmap editor. Roadmap information may explain schedule or attribution, but Product, Team Member, Bucket, Fiscal Month, Forecast, and Actual remain canonical.
- Future interface changes still require a frontend/interface version bump, a committed retrospective, a push to `develop`, and exact stage SHA verification before stakeholder testing.
