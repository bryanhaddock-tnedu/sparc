# Roadmap Billing Attribution Milestones

SPARC should use Jira roadmap data to explain and bill actual labor, not to replace Jira ticket ownership or become a roadmap editor.

## Milestone 1: Roadmap Actuals Foundation

Goal: make actual worklogs auditable by Roadmap Item on Product Detail and Team Member Detail.

- Keep Jira worklog sync as the source of actual hours.
- Add read-only Roadmap Item and Roadmap Item Issue Link records from Jira.
- Follow Jira parent relationships from each direct delivery link through descendant Epics, Stories, Tasks, and subtasks.
- Join `ActualEntry.source_ticket_key` to Roadmap Item Issue Links for reporting.
- Show mapped, unmapped, and ambiguous roadmap actuals on Product and Team Member detail pages.
- Do not mutate Forecast entries.

## Milestone 2: Mapping Quality And Billing Gaps

Goal: make billing blockers obvious before invoices or chargebacks are produced.

- Add an unmapped roadmap actuals queue.
- Add an ambiguous mapping queue when one ticket maps to more than one Roadmap Item.
- Add filters by Product, Team Member, Bucket, Fiscal Month, and Program Area.
- Add export-ready summaries for billing review.

## Milestone 3: Program Area Billing Views

Goal: summarize actual hours and calculated cost by Program Area and Roadmap Item.

- Add Program Area fields from roadmap data or manual SPARC mappings.
- Provide Product-level and cross-Product billing summaries.
- Preserve drill-through to Team Member, Jira ticket, and worklog evidence.

## Milestone 4: Roadmap Forecast Comparison

Goal: compare roadmap-item actuals to planning assumptions.

- Let Roadmap Items carry a default Product Bucket when available.
- Compare Roadmap Item actuals to forecast hours/cost without overwriting Forecast.
- Surface suggested forecast adjustments for human review.

## Milestone 5: Controlled Forecast Assistance

Goal: help update forecasts only after SPARC has strong evidence and approval rules.

- Generate proposed forecast changes from roadmap progress and Jira evidence.
- Require manager approval before modifying Forecast entries.
- Audit every accepted or rejected forecast recommendation.
