# SPARC Retrospective - 2026-07-15 10:55

## Retrospective Metadata

- Date: 2026-07-15
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Auditable Product and Roadmap attribution corrections
- Participants: Bryan Haddock, Florie, and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, and future SPARC Codex agents

## Stakeholder Request

Florie identified two correction cases with financial consequences:

1. Leadership may change which SPARC Product owns a Jira project after Team Members have logged time. Existing Jira Actual hours and dollars must move to the newly selected Product.
2. An admin may accidentally assign a Jira ticket to the wrong Roadmap Item. The ticket must remain visible and be assignable to a different Roadmap Item.

The prior Roadmap gap workflow only exposed ambiguous or unmapped tickets. A mapped ticket disappeared from the correction queue, and removing then recreating a Product Jira mapping did not immediately repair all stored historical Actual attribution.

## Domain Decisions

- Jira project-to-Product and Jira ticket-to-Roadmap Item corrections are separate operations because they change different ownership boundaries.
- `ProductJiraSpace` remains the single canonical Jira project-to-Product authority.
- A Product correction moves Jira-sourced Actual entries matching the Jira project key across every stored fiscal year. It also updates Product context on matching Roadmap issue links.
- A Product correction does not move Forecast entries, generated Estimates, manual Actual entries, or curated Product Team Member assignments.
- A ticket correction changes only Roadmap rollup attribution for the selected fiscal year. The canonical Actual Product, Team Member, Bucket, month, hours, and cost remain unchanged.
- A manual ticket correction outranks Jira-derived Roadmap links for that fiscal year and survives later Roadmap syncs until an admin changes or removes it.

## Implementation

- Added an atomic Admin-only Jira project move endpoint under Product Settings.
- Product Settings now provides a target Product selector and confirmation for each mapped Jira project.
- The confirmation states that all stored Jira Actuals move while Forecast and manual Actual rows stay unchanged.
- The success message reports the exact Actual entry count, hours, cost, and source/target Products.
- Historical Jira Actuals and Roadmap links that predate explicit project-key storage are matched by their exact Jira ticket-key prefix so they are not left under the old Product.
- Admin > Jira Sync now shows all Jira ticket attributions, including already mapped tickets, rather than only gaps.
- Ambiguous tickets continue to show only their competing Roadmap Item candidates; unmapped and mapped tickets can select from the fiscal-year Roadmap Item set.
- Roadmap changes require confirmation showing current and proposed attribution plus exact worklogs, hours, and dollars.
- Added immutable `AttributionChange` history with correction type, source key, before/after values, affected Actual count, hours, cost, actor snapshot, reason, and timestamp.
- Recent attribution history appears in Admin > Jira Sync.
- Attribution audit history is explicitly excluded from Admin Data export/import packages.

## Sync Behavior

- Daily Jira Actual sync continues to use the current canonical `ProductJiraSpace` mapping.
- The Product move corrects all stored fiscal years immediately, so historical data does not wait for another sync.
- Roadmap sync may refresh Jira-derived links and metadata, but it cannot recreate a competing link over a manual ticket correction in the same fiscal year.
- Roadmap sync and Actual sync remain independent; neither correction combines Forecast, Actual, Estimated, or Reported values.

## Data And Migration

- Added migration `0021_attr_changes` for the append-only attribution audit table.
- The migration identifier is 17 characters and remains within the deployment length constraint.
- No existing Product, Forecast, Actual, Estimate, Roadmap Item, or user table was repurposed.

## Verification

- Full backend suite: 111 tests passed.
- Regression coverage proves all-year Jira Actual movement, exclusion of manual Actuals and Forecasts, exact cost impact, legacy mapping alignment, fiscal-year-scoped Roadmap correction, audit capture, and manual correction precedence over later Roadmap sync.
- Frontend production build: passed.
- Fresh PostgreSQL migration chain through `0021_attr_changes`: passed.
- Alembic schema drift check: passed with no new upgrade operations detected.
- `git diff --check`: passed.
- Existing Vite large-chunk warning remains and was not introduced by this milestone.

## Versioning

- Root package version: `0.1.55`.
- Frontend/interface version: `0.1.92`.
- Version and migration identifiers remain short because overlong identifiers previously broke stage deployment.

## Stage Validation

1. Sign in as Admin and open Product Settings.
2. On a mapped Jira project, choose a different active Product and select Move.
3. Confirm the dialog states Jira Actuals move across stored fiscal years while Forecasts and manual Actuals do not.
4. Confirm the success message reports entries, hours, and dollars moved and the Jira project appears under the target Product.
5. Open Admin > Jira Sync and locate a ticket with status `mapped`.
6. Select a different Roadmap Item, review the financial impact confirmation, and confirm the change.
7. Confirm the ticket remains in Roadmap Ticket Attribution with the new Roadmap Item.
8. Confirm Recent Attribution Changes records both operations with source, before/after values, impact, actor, and time.
9. Run Roadmap sync and confirm the manually corrected ticket remains assigned to the chosen Roadmap Item.

## Collaboration Notes

- Bryan expects completed, testable milestones to be documented, committed, and pushed to `develop` so GitHub triggers stage deployment.
- Retrospectives are required handoff material and must preserve domain decisions, operational constraints, verification, and remaining risks.
- Stage is the stakeholder validation environment; Docker is appropriate for engineering verification.
- Keep momentum through planned milestones and interrupt only for a genuine blocker or a new stakeholder priority.
