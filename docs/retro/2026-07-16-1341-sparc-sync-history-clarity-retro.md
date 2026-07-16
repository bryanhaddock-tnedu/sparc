# SPARC Sync History Clarity Retrospective

## Session

- Date: 2026-07-16
- Milestone: Source-specific Jira Sync History results
- Participants: Bryan Haddock, Florie, and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, and future SPARC Codex agents

## Stakeholder Feedback

Florie asked why SPARC appeared to skip batches of records nearly every other sync and what `Skipped` actually meant. The history table alternated `jira` and `jira_roadmap` rows while applying the same Imported/Skipped headings to both jobs.

## Findings

- SPARC was not skipping alternating Jira API batches. Jira Actual worklogs are evaluated individually after Jira pagination completes.
- `jira` and `jira_roadmap` are separate sync jobs with different data and counter semantics.
- For Jira Actuals, `imported_count` means worklogs accepted into SPARC Actuals, including new and refreshed records.
- For Jira Actuals, `skipped_count` means worklogs excluded because Product, Team Member, or Work Type/Bucket mapping is unresolved.
- For completed Jira Roadmap runs, `imported_count` means Roadmap Items synchronized and `skipped_count` means stale Roadmap Items removed from the Fiscal Year.
- A repeated Jira Actual run re-evaluates the same current-fiscal-year worklogs idempotently, so unchanged accepted/excluded totals can appear again without creating duplicate Actuals.
- Sync History displayed only the completion date, making repeated same-day runs difficult to distinguish.
- The persisted history currently contains aggregate counts only. It cannot retrospectively divide an excluded worklog count by missing Team Member, Product, and Work Type reason.

## Implementation

- Replaced the raw `Source` identifier with `Jira Actuals`, `Jira Roadmap`, or a humanized fallback plus the sync type.
- Replaced generic Imported and Skipped columns with one source-aware Results column.
- Jira Actual rows now explicitly show worklogs accepted, worklogs excluded, and the mapping/classification conditions behind exclusion.
- Jira Roadmap rows now explicitly show Roadmap Items synchronized and stale items removed from the Fiscal Year.
- Failed Roadmap rows distinguish Roadmap Items processed from linked issues processed before failure.
- Failed runs display their stored error summary.
- Running or other in-progress states use a warning treatment instead of appearing as failures.
- Completion timestamps now include date, year, hour, and minute.
- Updated the product brief and build milestones to preserve these source-specific terms.
- Bumped the root release version to `0.1.62` and frontend/interface version to `0.1.99`.

## Verification

- Frontend TypeScript and Vite production build: passed.
- Full backend regression suite: 119 tests passed.
- `git diff --check`: passed.
- No backend behavior, database model, or migration changed.
- Local browser navigation and authentication succeeded. Full Admin rendering was blocked by the existing disposable Docker database, which was auto-created without Alembic history and predates current Roadmap columns. The database was left intact; this is not a regression from this interface change.
- Stage validation must confirm the live data presentation after deployment.

## Stage Acceptance Checklist

1. Sign in as Admin and open Admin > Jira.
2. Scroll to Sync History.
3. Confirm the old Imported and Skipped headings are gone.
4. Confirm `jira` rows now appear as Jira Actuals and explicitly show accepted and excluded worklogs.
5. Confirm excluded Jira Actual worklogs state that Team Member, Product, or Work Type mapping is unresolved.
6. Confirm `jira_roadmap` rows now appear as Jira Roadmap and explicitly show Roadmap Items synchronized and stale Fiscal Year items removed.
7. Confirm repeated runs on the same date show distinct completion times.

## Follow-up

The interface now accurately explains the aggregate history that SPARC stores. A future observability milestone should persist per-reason exclusion counts or worklog-level exclusion details so an Admin can identify the exact Team Member, Product, or Work Type issue behind a number such as 84 without rerunning or manually reconciling Jira.
