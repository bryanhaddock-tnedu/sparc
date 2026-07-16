# Roadmap Billing Attribution Milestones

SPARC should use Jira roadmap data to explain and bill actual labor, not to replace Jira ticket ownership or become a roadmap editor.

## Current Status

All five implementation milestones are complete in stage. The active work is stakeholder acceptance against real Jira data, not another Roadmap data-model build.

Stakeholder acceptance checklist:

- [ ] Review the remaining unmapped and ambiguous tickets after sync and distinguish genuine Jira gaps from competing Roadmap relationships.
- [ ] Verify ambiguous tickets list only their inferred competing Roadmap Items.
- [x] Verify already-mapped tickets can be corrected, financial impact is confirmed, and manual corrections survive later Roadmap syncs. Florie accepted this flow on July 16, 2026.
- [ ] Verify Jira project-to-Product corrections move only applicable Jira Actuals and preserve Forecast and curated roster data.
- [ ] Verify filters, billing summaries, CSV exports, forecast comparison, applied/rejected recommendations, and immutable audit history with Florie.

## Milestone 1: Roadmap Actuals Foundation

**Status**: Complete

Goal: make actual worklogs auditable by Roadmap Item on Product Detail and Team Member Detail.

- Keep Jira worklog sync as the source of actual hours.
- Add read-only Roadmap Item and Roadmap Item Issue Link records from Jira.
- Follow Jira parent relationships from each direct delivery link through descendant Epics, Stories, Tasks, and subtasks.
- Join `ActualEntry.source_ticket_key` to Roadmap Item Issue Links for reporting.
- Show mapped, unmapped, and ambiguous roadmap actuals on Product and Team Member detail pages.
- Do not mutate Forecast entries.

## Milestone 2: Mapping Quality And Billing Gaps

**Status**: Complete

Goal: make billing blockers obvious before invoices or chargebacks are produced.

- Add an unmapped roadmap actuals queue.
- Add an ambiguous mapping queue when one ticket maps to more than one Roadmap Item.
- Add filters by Product, Team Member, Bucket, Fiscal Month, and Program Area.
- Add export-ready summaries for billing review.

## Milestone 3: Program Area Billing Views

**Status**: Complete

Goal: summarize actual hours and calculated cost by Program Area and Roadmap Item.

- Add Program Area fields from roadmap data or manual SPARC mappings.
- Provide Product-level and cross-Product billing summaries.
- Preserve drill-through to Team Member, Jira ticket, and worklog evidence.

## Milestone 4: Roadmap Forecast Comparison

**Status**: Complete

Goal: compare roadmap-item actuals to planning assumptions.

- Let Roadmap Items carry a default Product Bucket when available.
- Compare Roadmap Item actuals to forecast hours/cost without overwriting Forecast.
- Surface suggested forecast adjustments for human review.

## Milestone 5: Controlled Forecast Assistance

**Status**: Complete for the current approval model

Goal: help update forecasts only after SPARC has strong evidence and approval rules.

- Generate proposed forecast changes from roadmap progress and Jira evidence.
- Require manager approval before modifying Forecast entries.
- Audit every accepted or rejected forecast recommendation.

## Guardrails

- Worklog sync owns Actual hours; Roadmap sync owns Roadmap Items and issue relationships.
- Forecast remains canonical at Product + Team Member + Bucket + Fiscal Month/Fiscal Year.
- Roadmap sync must never create or overwrite Actual or Forecast entries.
- `Product.office` remains the Program Area authorization boundary; `RoadmapItem.program_area` is descriptive Jira metadata only.
- Manual ticket attribution corrections are fiscal-year scoped, audited, and authoritative until changed or removed by an Admin.
