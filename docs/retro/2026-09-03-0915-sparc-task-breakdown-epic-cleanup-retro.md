# SPARC-3 Task Breakdown Epic Cleanup Retrospective

## Summary

Adjusted the Task Level Forecast Breakdown after Florie clarified that Epics should remain higher-level containers and PO hours should be logged to the actual work tickets going forward. The normal Program Area/Leadership receipt list should focus on costable work tickets, not Epic container rows.

## Implementation

- Added `actual_entries.source_issue_type` and updated Jira sync to persist the Jira issue type with actual worklogs.
- Excluded rows with Jira issue type `Epic` from the Task Level Forecast Breakdown once issue type has been synced.
- Removed the role-level actual breakdown from ticket receipt API responses and cards.
- Improved unavailable estimate status text:
  - `No story points`
  - `No Jira Team`
  - `No matching Jira Team profile`
  - `Missing active role rate`
- Treated the `Product` Team Member role label as Product Owner for estimate role-rate averages.
- Required positive active rates for all estimate roles so unset FTE rates do not silently reduce estimated cost.

## Notes

Existing synced UAT worklogs need a fresh Jira Actuals sync before historical Epic rows can be excluded by issue type. Until the sync refreshes those rows, older entries may not have `source_issue_type` populated.
