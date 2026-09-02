# SPARC-3 Ticket Cost Receipts Retrospective

## Outcome

Implemented the first SPARC-3 Product Detail ticket-cost receipt. Authorized Admin, Leadership, and Program Area viewers can see fiscal-month ticket containers with Jira ticket key/summary, story points, estimated cost, actual cost, variance, and role-level actual hours/cost. The response omits contributor names and bill rates.

## Estimation model

The app-owned Jira Actual sync now stores a ticket summary, Jira Team, and Story Points with each worklog. Admins can create or update an independent Jira Team Estimation Profile in Estimation Settings. The profile supplies velocity, Developer capacity hours, QA percent, and Product Owner percent. Product Maintenance can be configured with the approved 75.8-point velocity, 360 Developer capacity hours, 20% QA, and 15% Product Owner inputs.

For an eligible ticket, Developer estimated hours are `story points / Jira Team velocity * Developer capacity`. The blended active `Dev`/`Sr. Dev` rate is used only for the Developer estimate; active QA and Product Owner role averages apply to their configured portions. Actual role totals retain the exact Team Member job titles and calculate from actual logged hours and current bill rates.

Follow-up iteration on 2026-09-02 renamed the Product Detail section to `Task Level Forecast Breakdown`, removed the explanatory redaction sentence from its subheader, added each ticket's work type with bucket-aligned badge styling, and grouped tickets into collapsible fiscal-month sections so prior months do not dominate the page. A data migration seeds the Product Maintenance Jira Team estimation profile with the approved starting assumptions when no matching profile exists.

Profiles do not map to SPARC Team rosters and do not alter individual-contributor Forecast entry. Tickets without story points or an active matching Jira Team profile remain visible with actual work and an explanatory unavailable-estimate status.

## Verification

- `python3 -m compileall -q backend/app`
- Focused backend/migration/auth/access/service tests: **111 passed**.
- Clean Dockerfile Node 22 TypeScript/Vite build passed for interface `0.1.108`.

## Release

- Interface version: `0.1.107` to `0.1.108`
- Root release version: `0.1.70` to `0.1.71`
- Database migration: `0023_ticket_cost_receipts`

## UAT deployment follow-up

UAT deployed the SPARC-3 image before applying `0023_ticket_cost_receipts`, causing Product Detail to return Internal Server Error when the new ticket-cost endpoint queried its new ActualEntry columns. The container startup now runs `alembic upgrade head` before Uvicorn starts, so the app will not serve a new image against a prior database schema.

After that migration fix deployed, UAT exposed a second receipt-service defect: Team Member uses the existing `status` field, not an `is_active` field. The rate-average query now correctly selects `status = active`; receipt data can no longer fail because of that invalid model attribute.
