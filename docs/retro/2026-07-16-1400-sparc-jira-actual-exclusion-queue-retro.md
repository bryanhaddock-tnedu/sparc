# SPARC Jira Actual Exclusion Queue Retrospective

## Session

- Date: 2026-07-16
- Milestone: Ticket-level Jira Actual exclusion diagnostics
- Participants: Bryan Haddock, Florie, and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, and future SPARC Codex agents

## Stakeholder Feedback

The source-specific Sync History update made `Skipped` understandable as excluded Jira worklogs, but Florie still had no SPARC-native way to identify the affected tickets. Missing Work Type could be diagnosed with a separate JQL report and corrected in Jira, while unmapped users and projects were corrected in SPARC. The interface needed to show the exact tickets and make correction ownership explicit.

## Decision

SPARC now treats a Jira Actual exclusion as durable sync evidence, not merely an aggregate counter. Each live sync records one exclusion row per rejected worklog. The Admin Jira page groups the latest completed live run by ticket and explains every reason that kept its worklogs out of canonical Actuals.

Correction ownership is intentionally split:

- Missing or unrecognized Work Type is corrected on the Jira ticket.
- Unmapped Jira identity is corrected in Admin > Jira > Jira Users.
- Unmapped Jira project is corrected through Product Settings.
- After correction, an Admin reruns Jira Actuals; the worklog then enters Actuals through the existing idempotent sync path.

This queue is independent of Roadmap attribution. It does not create or change Forecasts, Roadmap Items, Roadmap ticket mappings, bill rates, or existing accepted Actual values.

## Implementation

- Added `JiraWorklogExclusion`, owned by `SyncRun`, with Jira issue/worklog identity, ticket and project context, Jira user, worked date, hours, raw Work Type, and invalid Work Type/unmapped user/unmapped Product flags.
- Added Alembic revision `0022_sync_gaps`; the short revision ID complies with the 32-character stage deployment limit.
- Live and mock normalization record exclusion evidence before an unresolved worklog is counted as excluded.
- Added an Admin-only `GET /api/integrations/jira-rovo/worklog-exclusions` endpoint.
- The endpoint reads only the latest completed live `jira` run, so a local mock sync cannot replace the operational queue.
- The endpoint groups worklogs by ticket and returns worklog count, excluded hours, date range, Jira users, raw Work Type values, Jira link, and reason codes.
- Added Jira Actual Exclusions directly below the Jira status cards in Admin > Jira so the correction queue is visible near the sync controls.
- The manual-sync success message now uses accepted/excluded Actual terminology and directs the Admin to the correction queue.
- Missing and unrecognized Work Types have distinct labels and Jira correction instructions.
- Unmapped users link to the Jira Users section; unmapped projects link to Product Settings.
- Older syncs keep their aggregate excluded count. The interface asks for one new Jira Actuals sync when those historical runs lack ticket detail.
- Bumped root release version to `0.1.63` and frontend/interface version to `0.1.100`.

## Guardrails Preserved

- Actuals remain read-only Jira-sourced values and are imported only when Product, Team Member, and Bucket resolve.
- Unknown Work Type does not default to Maintenance or another Bucket.
- Unknown Jira projects do not default to Core Infrastructure.
- The queue is backend Admin-protected; UI visibility is not the authorization boundary.
- Accepted Jira worklogs remain idempotent by source issue/worklog identity.
- Roadmap sync and Roadmap attribution remain separate from Jira Actual ingestion.

## Verification

- Full backend regression suite: 121 tests passed.
- Frontend TypeScript and Vite production build: passed.
- Fresh PostgreSQL migration from revision 0001 through `0022_sync_gaps`: passed.
- Migration identifier length regression test: passed as part of the backend suite.
- `git diff --check`: passed.
- Local browser verification against a fresh migrated PostgreSQL database: passed.
- Verified empty, populated, missing Work Type, unrecognized Work Type, and combined unmapped-user resolution states with no browser console errors.

## Stage Acceptance Checklist

1. Sign in as Admin and open Admin > Jira.
2. Find Jira Actual Exclusions above Jira Users.
3. Because the current stage run predates this feature, confirm SPARC requests one new Jira Actuals sync instead of inventing ticket detail.
4. Run Sync Jira Actuals once.
5. Confirm the aggregate excluded worklog count now has ticket rows with Project, Work Type, Jira User, excluded hours, worklog count, and date range.
6. Open a ticket marked Missing Work Type, set Jira Work Type to Net New, Enhance, or Maintenance, and rerun Jira Actuals.
7. Confirm the corrected ticket leaves the queue and its worklogs enter Actuals.
8. For an Unmapped Jira User row, use Map Jira user in SPARC, assign the Team Member, and rerun Jira Actuals.
9. For an Unmapped Product row, use Product Settings to assign the Jira project to its canonical Product, and rerun Jira Actuals.
10. Confirm Program Area, Forecast, Roadmap attribution, and bill-rate behavior are unchanged.

## Operational Note

The queue shows the latest completed live Jira Actuals run, which is the actionable state after the scheduled morning sync or a manual resync. Historical aggregate-only runs cannot be reconstructed after the fact because SPARC did not previously persist their rejected worklog evidence.
