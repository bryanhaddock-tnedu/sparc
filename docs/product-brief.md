# SPARC Product Brief

SPARC is the internal labor forecasting and cost intelligence app for this project.

## Project Purpose

Build an internal labor forecasting and cost intelligence web app for a State Department of Education IT team.

This is not a project management tool. Do not add task boards, sprint planning, timeline management, due dates, or Gantt charts unless explicitly requested.

## Canonical Terms

- Use Product, not Project, as the primary work entity.
- Every Product can map to one or more Jira spaces/projects.
- Use Team Member for people/labor resources.
- Use Bucket for work type: Net New, Enhance, Maintenance.
- Forecast hours are manually entered in this app.
- Actual hours come from Jira/Rovo API.
- Roadmap Items are read-only Jira roadmap records used to attribute actual hours to product roadmap entries for billing and program-area reporting.
- Estimated hours are model-generated from Jira issue/activity evidence when actual time logging is incomplete.
- Reported/Effective hours are derived by policy and must never overwrite Forecast, Actual, or Estimated source values.
- Cost is calculated as hours multiplied by bill rate.
- Product budget is fiscal-year specific and stored per Product + Fiscal Year.
- Projected spend is the full-year forecasted cost.

## Architecture

Use a monorepo:

- frontend: React + TypeScript
- backend: Python FastAPI
- database: PostgreSQL
- local development: Docker Compose

## UI / Styling

- Use Tailwind CSS for styling.
- Use shadcn/ui for common UI components.
- Do not use Bootstrap.
- Use Recharts for charts.
- Use TanStack Table or AG Grid for data-heavy tables.
- Brand palette:
  - Primary red: `#D22730`
  - Primary navy: `#002D72`
  - Primary gray: `#76777A`
  - Supporting cyan: `#2CCCD3`
  - Supporting lime: `#D2D755`
  - Supporting orange: `#E87722`
  - Supporting slate teal: `#5E7975`

## UI Principles

- Keep navigation contextual.
- Maintain only a Dashboard link as persistent navigation.
- Products and Team Members must be clickable wherever the viewer has access to the destination page.
- Dashboard summarizes Products.
- Product Detail is the main analytical page.
- Team Member Detail shows the inverse view across Products.
- Keep tables data-dense but readable.
- Monthly forecast-entry grids must fit the full July-through-June Fiscal Year in the visible panel without horizontal scrolling; shrink month cells before introducing scroll.
- Do not create a large traditional nav menu unless explicitly requested.

## Data Rules

- Fiscal year runs July through June.
- Forecast hours are editable.
- Actual hours are read-only from Jira/Rovo.
- Estimated hours are read-only generated values tied to an Estimation Run.
- Reported/Effective hours are derived for reporting using a visible rule:
  - If the month is closed and Actual is at least 75% of Estimated, use Actual.
  - Else if Estimated exists, use Estimated.
  - Else if the month is future/planning and Forecast exists, use Forecast.
  - Else use 0.
- Forecast, Actual, Estimated, and Reported/Effective values must remain separate.
- Every generated number should preserve enough context to explain where it came from.
- Cost values are calculated, not manually entered.
- Bill rate can be updated after spreadsheet import.
- MVP uses current bill rate for calculations.
- Future state may add bill rate versioning.
- Budget tracker compares Budgeted, Forecast, and Actuals using a compact horizontal bar.
- Team Member ID is optional and system-generated if not provided.
- Team Members default to active.
- Products may be tagged with Office and Division for organizational reporting. Office options are Academics, Operations, Programs, Deputy Commissioner, Commissioners Office, and General Counsel; Division options are constrained by the selected Office.
- For access-control planning, Product Office is the SPARC Program Area source of truth. User-facing labels should move toward Program Area where this concept is used for reporting or visibility. Product Division is lower-level reporting metadata, not the initial security boundary.
- Roadmap Item Program Area is source/display metadata only and must not be used for authorization. Program Area View Only access must be scoped through the mapped Product's Program Area (`Product.office`).
- Product detail URLs use lowercase dash slugs derived from Product names, for example `/products/core-infrastructure`; numeric Product IDs remain accepted only as backwards-compatible references.
- Team Member detail URLs use lowercase dash slugs derived from Team Member names, for example `/team-members/avery-johnson`; numeric Team Member IDs remain accepted only as backwards-compatible references.
- Roadmap sync and worklog sync are separate pipelines. Worklog sync owns actual hours; roadmap sync owns Roadmap Items and ticket relationships; SPARC reporting joins them by Jira ticket key.
- Roadmap sync must follow the Jira parent hierarchy beneath each directly linked delivery work item so work logged on descendant Epics, Stories, Tasks, or subtasks can roll up to the Roadmap Item. The original Actual ticket key remains unchanged and auditable.
- Roadmap Actual Gaps must show only the competing Roadmap Items when a ticket is ambiguous. A truly unmapped ticket may show all fiscal-year Roadmap Items because it has no inferred candidates.
- Admins must be able to correct a Jira project's canonical Product owner from Product Settings. The correction moves all Jira-sourced Actual entries for that Jira project across stored fiscal years and updates Product context on linked Roadmap work. It must not move Forecast entries, generated Estimates, manual Actual entries, or curated Product Team Member assignments.
- Admins must be able to reassign any Jira Actual ticket, including an already mapped ticket, to a different Roadmap Item for the selected fiscal year. This changes Roadmap rollup attribution only; it does not change the Actual entry's Product, Team Member, Bucket, month, hours, or cost.
- A manual Jira ticket-to-Roadmap Item correction is authoritative for that fiscal year and must survive later Roadmap syncs until an admin changes or removes it.
- Product and Roadmap attribution corrections must require confirmation, report the affected Actual entry/worklog count, hours, and cost, and append immutable audit history with actor, before/after values, reason, and timestamp.
- Created date and last updated date are required.

## Access Model

Entra authenticates users; SPARC authorizes users locally.

Initial SPARC roles:

- Admin: can view and edit everything; can see hours, costs, and bill rates; can run admin, sync, import, and configuration operations.
- Leadership View Only: can view all Program Areas; cannot edit; can see aggregate hours and costs plus Team Member names as plain-text Report dimensions; cannot see bill rates, detailed Product labor, Product Team rostering, Product-by-Bucket Forecast tables, Team Member profiles, Team Management, or Team Analytics. Restricted fields and sections must be omitted rather than labeled as hidden.
- Program Area View Only: can view only assigned Program Area(s); cannot edit; cannot see bill rates; can be assigned multiple Program Areas.

Program Area assignment rows apply only to Program Area View Only users. Admin and Leadership View Only users see all Program Areas by role. Changing a user from Program Area View Only to either broader role must clear the user's stored Program Area assignments atomically; changing unrelated fields must preserve unchanged assignments without deleting and recreating them.

The existing `sparc` basic login remains the break-glass Admin login while Entra SSO is implemented and validated. Other users should be stored as email-based SPARC user records with temporary local password hashes before SSO; those same records should later link to Entra tenant/object IDs after first SSO login.

After a successful sign-in, SPARC should land the user on the Dashboard rather than preserving a pre-login Admin or otherwise restricted URL. Direct restricted-route access must remain denied by the frontend capability gate and the backend authorization layer.

Program Area View Only filtering must use:

```text
Product.office IN current_user.assigned_program_areas
```

Users with Program Area View Only and no assigned Program Area should receive no scoped SPARC data and a clear no-assignment state.

## Product Buckets

Each Product has three buckets:

1. Net New
2. Enhance
3. Maintenance

Admin Product Detail pages must organize detailed labor data by these buckets. Leadership and Program Area views retain only the aggregate Product information permitted by their role.

## Required Pages

Build these primary routes:

- `/` — Dashboard
- `/products/:productSlug` — Product Detail
- `/products/settings` — Product Settings
- `/teams/:teamSlug` — Team Analytics
- `/team-members/:teamMemberSlug` — Team Member Detail
- `/team` — Team Management
- `/reports` — Enterprise Reports

Team Management and Team Analytics routes are Admin-only. Leadership may still use Team as a report dimension and see Team Member names in permitted Product and Report views without receiving links into restricted Team or Team Member pages.

## Dashboard Requirements

The Dashboard should include:

1. Strategic summary metric cards at the top.
2. Product summary table underneath.
3. Clickable Product names that navigate to Product Detail pages.

Dashboard summary cards should include:

- Budget Tracker
- FY Forecasted Cost
- FYTD Actualized Cost
- Remaining Forecasted Cost
- FYTD Actualized Hours
- Forecasted Hours
- Cost Variance

Product summary table columns:

- Product
- # Team Members
- Forecasted Hours
- Forecasted Cost
- FYTD Hours
- FYTD Cost

Optional columns if useful:

- Remaining Hours
- Remaining Cost
- % Forecast Consumed
- Variance Cost

## Product Detail Page Requirements

Each Product Detail page should include:

Leadership View Only receives the Product header, Budget Tracker, aggregate Product snapshot, and aggregate actual-hours bucket distribution. Product Team, role-cost breakdown, Product-by-Bucket Forecast matrices, Reported Values, and their raw supporting APIs are Admin-only. Program Area View Only receives the same high-level Product page further redacted by its no-hours capability. These visibility rules must not delete or alter Product Team, Forecast, Actual, Estimate, Roadmap, or Jira data.

1. Product header
   - Product name
   - Jira space key/reference badges
   - Office and Division badges, if available
   - Product description, if available
   - Active/inactive status

2. Bucket distribution pie chart
   - Shows FYTD actualized hours distribution across:
     - Net New
     - Enhance
     - Maintenance

3. Hours metric cards
   - Actualized Hours FYTD
   - Forecasted Hours FY
   - Remaining Hours

4. Cost metric cards
   - Actualized Cost FYTD
   - Forecasted Cost FY
   - Remaining Cost

5. Budget Tracker
   - Shows Product Budgeted, Forecast, and Actuals for the selected Fiscal Year

6. Roadmap Actuals
   - Shows actual hours and calculated cost grouped by Roadmap Item, Team Member, and Bucket
   - Flags actuals with no Roadmap Item mapping as unmapped
   - Flags tickets linked to multiple Roadmap Items as ambiguous

Product Forecast lines may be removed for a selected fiscal year only when the Product + Team Member + Bucket line has zero Forecast hours and no Actual labor. Removing an empty Forecast line deletes only those zero-value Forecast placeholders; it must retain Product Team membership and must never delete Actual entries.

7. Product Team
   - Shows manager-curated team members assigned to the Product
   - Allows adding rostered Team Members to the Product before forecast/actual hours exist
   - Allows editing default bucket and product assignment status
   - Allows removing a Team Member from the Product assignment list without deleting historical forecast/actual rows

8. Three Product-specific data sections:
   - Net New
   - Enhance
   - Maintenance

Each bucket section should include a monthly matrix table:

| Team Member | Metric | Jul | Aug | Sep | Oct | Nov | Dec | Jan | Feb | Mar | Apr | May | Jun | FY Total |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|

Rules:

- One row per Team Member contributing to that Product + Bucket.
- Each Team Member group has left-side metric labels for Forecast, Actual, Forecast cost, and Variance.
- Final row group should be Bucket Total.
- Team Member names are clickable.
- Forecast Hours cells are editable.
- Actual Hours cells are read-only.
- Cost cells are read-only calculated values.
- Cost variance cells are read-only calculated values using Actual cost minus Forecast cost. Negative values mean actuals are under forecast; positive values mean actuals exceeded forecast.

## Product Settings Page Requirements

Product Settings should be an editable table for product-level configuration and Jira mapping.

Columns:

- Product name
- Jira spaces/projects
- Office
- Division
- Fiscal Year Budget
- Status
- Description
- Last Updated

Rules:

- Product detail remains accessible from each row.
- New Products can be added from this page.
- Office and Division are editable dropdown selectors.
- Division options depend on the selected Office.
- Budget is editable per selected Fiscal Year and drives the dashboard/product budget tracker.
- Jira mappings are one-to-many: one SPARC Product can contain multiple Jira spaces/projects.
- A Jira space/project should only map to one SPARC Product to avoid double-counting actual hours.
- Jira spaces can be selected from the server-side Jira project catalogue.
- Users can refresh the Jira project catalogue through an app-owned backend API call.
- Users can manually enter a Jira key when the catalogue has not been refreshed yet.
- Saved Jira mappings can be validated through a backend check that confirms the Jira key exists and is visible to the integration account.
- Product active/inactive status is editable.
- Created date and updated date are maintained by the backend.

## Team Member Detail Page Requirements

Each Team Member Detail page should include:

1. Profile section
   - Name
   - Role
   - Team
   - Bill rate
   - Employment type
   - Contracting company
   - Active status
   - Created date
   - Last updated date

2. Product associations table

   - Includes a monthly Forecast by Product and Bucket table backed by canonical Forecast entries.
   - Active Team Members may add a Product + Bucket Forecast line without overwriting an existing Product Team default bucket.
   - Empty Forecast lines may be removed only when Forecast hours are zero and no Actual labor exists; Product Team membership remains.

3. Budget Tracker
   - Shows Team Member forecast and actuals for the selected Fiscal Year

4. Roadmap Actuals
   - Shows actual hours and calculated cost grouped by Roadmap Item, Product, and Bucket
   - Preserves Jira ticket evidence for billing review
   - Flags unmapped or ambiguous Roadmap Item attribution

Columns:

- Product
- Bucket
- Forecast Hours
- Actual Hours
- Forecast Cost
- Actual Cost
- Remaining Cost

Rules:

- Product names are clickable.
- Product links navigate back to Product Detail pages.

## Team Management Page Requirements

Team Management is an Admin-only page. It should be a searchable, sortable roster grouped by Team. Each Team group should render its own roster table and link to a team-specific analytics page.

The page should also include an all-Team-Member ranking table with a dimension selector for hours, ticket, and story point signals. These rankings are context signals only; they must not be labeled as performance scores.

Columns:

- Name
- Role
- Bill Rate
- Employment Type
- Contracting Company
- Status
- Last Updated

Rules:

- Name links to Team Member Detail page.
- Team Member Detail links use lowercase dash slugs derived from Team Member names.
- Active status defaults to active.
- Team appears as the group heading instead of a repeated table column.
- Team headings link to Team Analytics pages.
- Team Analytics URLs use lowercase dash slugs derived from Team names, for example `/teams/agency-technology`; encoded spaces or capitalized Team names are not used in generated links.
- Roster tables can be sorted by clicking column headers.
- Name search should match typed prefixes for first or last names.
- Bill Rate is read-only on the Team Management table.
- Bill rates can be updated from the Team Member Detail profile after import.
- Rate changes affect future forecasting calculations.
- Created date and updated date are maintained by the backend.

## Team Analytics Page Requirements

Team Analytics is an Admin-only page and should summarize one Team at a time.

The page should include:

- Active and inactive Team Member counts.
- FYTD actual hours.
- FY forecast hours.
- Products supported.
- Primary Product and primary work type.
- Monthly forecast versus actual hours.
- Product Forecast Planner grouped by Product and Bucket with Team Member rows and fiscal-month Forecast inputs.
- Delivery Flow section that separates In Engineering, Engineering Work Done, Business Acceptance, and Business Accepted / Done.
- Team Member ranking table with a dimension selector.
- Product, work type, and role mix tables.

Ranking dimensions may include actual hours, average hours per month, forecast hours, actual-versus-forecast hours, products supported, tickets touched, story points, hours per ticket, hours per story point, and story points per logged hour.

Rules:

- Story point ratios are context signals, not productivity scores.
- Story points should be counted once per unique Jira issue, even if an issue is allocated across multiple months.
- Ratio values with no denominator should display as unavailable rather than zero.
- Engineering Work Done should represent Jira statuses such as Ready for UAT, Ready for Acceptance, Dev Complete, or Code Complete.
- Business Acceptance should represent Jira statuses such as In UAT, Business Acceptance, Business Review, Awaiting Acceptance, or Signoff.
- Delivery-flow aging should use the latest Jira updated date until SPARC captures explicit Jira status-transition dates.
- Product Forecast Planner writes canonical Product + Team Member + Bucket + Fiscal Month/Fiscal Year Forecast entries shared with Product Detail and Team Member Detail.
- Team Actual totals use canonical Jira Actual entries for Team Members on the selected Team, including Actuals with unresolved Roadmap attribution. Product-wide labor from other Teams must not be included.
- Product Program Area in Team planning comes from `Product.office`. Roadmap Item Program Area/Agency Office and source Team are context only and must not grant Product ownership to a Team.
- Jira Roadmap schedule dates may highlight planning months but must not become Forecast ownership or Forecast grain.
- Saving one or more Team Forecast cells updates only the submitted cells and must never clear untouched fiscal months.
- Invalid Forecast input must remain unsaved and visibly invalid; it must never be coerced to zero.
- Inactive Products and inactive Team Members may remain visible for history but cannot receive new Team Forecast entries.
- Team Management, Team Analytics, and the Team planning API are Admin-only.
- Seeing a Team Member or Team name in a permitted Product or Report view is separate from page access. Leadership names render as plain text, direct Team and Team Member routes and APIs are denied, and rate or rate-derived fields are omitted instead of displaying a `Hidden` placeholder.

## Enterprise Reports Page Requirements

Enterprise Reports should provide adjustable labor cost rollups without becoming a project management view.

Initial report:

- Labor Cost Report

Supported dimensions:

- Person
- Role
- Employment Type
- Team
- Product
- Bucket

Rules:

- Reports are scoped to the selected Fiscal Year.
- Users can select which dimension is the lead column and optionally add second, third, and fourth dimensions.
- Cost values are calculated from Forecast or Actual hours multiplied by Team Member bill rate.
- Product and Person values link to their detail pages.
- Reports must be viewable in SPARC and exportable as `.xlsx`.
- Export filenames should use the report name and current date in `yyyymmdd` format, for example `labor-cost-report-20260702.xlsx`.

## Backend Requirements

Use FastAPI.

Do not put business logic directly in route handlers.

Use service modules for:

- cost calculations
- dashboard aggregation
- fiscal year logic
- Jira/Rovo normalization
- forecast upserts
- estimation policy and Jira issue activity estimation
- reported/effective value selection

## Database Entities

Implement:

- Product
- TeamMember
- Bucket
- FiscalMonth
- ForecastEntry
- ActualEntry
- RoadmapItem
- RoadmapItemIssueLink
- JiraUserMapping
- JiraProductMapping
- JiraProjectCatalog
- ProductJiraSpace
- EstimationProfile
- EstimationRun
- EstimatedEntry
- EstimatedIssueAllocation
- AppUser
- UserProgramAreaAssignment
- ProductBudget
- ProductTeamMember
- ForecastRecommendationDecision

`JiraProductMapping` is a discovery/review cache, not a Product attribution authority. `ProductJiraSpace` is the only persisted Jira project-to-Product authority. The former `RoadmapForecastAllocation` persistence model is retired; all planning hours use canonical `ForecastEntry` rows.

Seed the three buckets:

- NET_NEW
- ENHANCE
- MAINTENANCE

## API Requirements

Create API endpoints for:

Dashboard:

- `GET /api/dashboard/summary?fiscal_year=2026`
- `GET /api/dashboard/products?fiscal_year=2026`

Products:

- `GET /api/products`
- `POST /api/products`
- `GET /api/products/{product_id}`
- `PUT /api/products/{product_id}`
- `GET /api/products/{product_id}/summary?fiscal_year=2026`
- `GET /api/products/{product_id}/bucket-distribution?fiscal_year=2026`
- `GET /api/products/{product_id}/bucket-tables?fiscal_year=2026&metric=hours&data_type=forecast`
- `GET /api/products/{product_id}/jira-spaces`
- `POST /api/products/{product_id}/jira-spaces`
- `PUT /api/products/{product_id}/jira-spaces/{space_id}`
- `DELETE /api/products/{product_id}/jira-spaces/{space_id}`
- `POST /api/products/{product_id}/jira-spaces/{space_id}/validate`
- `POST /api/products/{product_id}/jira-spaces/{space_id}/move`
- `GET /api/products/{product_ref}/roadmap-actuals?fiscal_year=2026`

Team Members:

- `GET /api/team-members`
- `POST /api/team-members`
- `GET /api/team-members/{team_member_ref}`
- `PUT /api/team-members/{team_member_ref}`
- `GET /api/team-members/{team_member_ref}/products?fiscal_year=2026`
- `GET /api/team-members/{team_member_ref}/roadmap-actuals?fiscal_year=2026`

Forecasts:

- `GET /api/forecasts?product_id=&team_member_id=&fiscal_year=`
- `PUT /api/forecasts`

Jira/Rovo:

- `GET /api/integrations/jira-rovo/status`
- `POST /api/integrations/jira-rovo/sync`
- `POST /api/integrations/jira-rovo/sync-live`
- `GET /api/integrations/jira-rovo/worklog-exclusions`
- `POST /api/integrations/jira-rovo/roadmap/sync`
- `GET /api/integrations/jira-rovo/roadmap/items`
- `GET /api/integrations/jira-rovo/roadmap/forecast-recommendation-decisions`
- `POST /api/integrations/jira-rovo/roadmap/forecast-recommendation-decisions`
- `PUT /api/integrations/jira-rovo/roadmap/ticket-links/{ticket_key}`
- `GET /api/integrations/jira-rovo/attribution-changes`
- `GET /api/integrations/jira-rovo/unmapped-users`
- `GET /api/integrations/jira-rovo/unmapped-products`
- `GET /api/integrations/jira-rovo/project-catalog`
- `POST /api/integrations/jira-rovo/project-catalog/refresh`

Estimations:

- `GET /api/estimations/profiles`
- `PUT /api/estimations/profiles/{profile_id}`
- `GET /api/estimations/runs?fiscal_year=2026`
- `POST /api/estimations/preview`
- `POST /api/estimations/run`
- `GET /api/estimations/runs/{run_id}/allocations`
- `GET /api/estimations/story-point-metrics?fiscal_year=2026`
- `GET /api/estimations/delivery-flow?fiscal_year=2026`
- `GET /api/estimations/reported-values?fiscal_year=2026&product_id=&team_member_id=`

## Jira/Rovo Integration

Actual hours come from Jira through app-owned backend integration code.

Local/demo environments may use the mock sync, but real environments should use the live Jira sync endpoint with credentials supplied only through server-side environment variables or Key Vault.

Roadmap Items come from a separate roadmap sync. That sync must never create or overwrite ActualEntry rows. It only stores Roadmap Items and their relationships to directly linked Jira delivery work and its parent-hierarchy descendants so Product and Team Member pages can attribute actual hours for billing review.

Forecast adjustment review on the Admin Jira Sync page is a full-fiscal-year Product + Bucket comparison of canonical Forecast hours to mapped Roadmap Actual hours. Applying a recommendation adds only the reviewed delta to an explicit Team Member and Fiscal Month Forecast line after verifying that the reviewed totals are still current. Dismissing a recommendation changes no Forecast or Actual data and hides that exact snapshot until its totals change. Every decision remains in immutable history.

Roadmap Item inclusion is intentionally fiscal-year scoped. A Jira Product Discovery record must be in the configured roadmap project, use the `Idea` issue type, carry the exact fiscal-year label such as `FY27`, and be visible to the Jira integration account. Product mapping affects attribution after import; it does not determine whether the Idea is fetched.

The app should:

1. Query Jira ticket/worklog data from backend code only.
2. Extract hours worked from Jira worklogs.
3. Identify Jira user.
4. Identify Jira space/project and its mapped SPARC Product.
5. Identify bucket if Jira has bucket/type data.
6. Normalize worklog dates into fiscal months.
7. Store actual hours.
8. Surface worklogs excluded because Work Type, Team Member, or Product cannot be resolved.

Jira credentials must remain server-side. The app owns Jira access; AI tools should only call app codepaths.

Live Jira Actuals sync must run automatically once every morning before 8am Central time. The default schedule is 7:30am `America/Chicago`. Automatic sync uses the same app-owned backend codepath as manual Jira Actuals sync, syncs the current fiscal year, and skips when a live sync already ran that Central-time day.

Sync History must present source-specific results rather than generic Imported/Skipped counters. Jira Actuals runs report worklogs accepted into Actuals and worklogs excluded because Team Member, Product, or Work Type mapping is unresolved. Jira Roadmap runs report Roadmap Items synchronized and stale items removed from the selected Fiscal Year. Accepted and synchronized counts include both new and refreshed records. Completion timestamps include time so repeated same-day runs are distinguishable.

The Admin Jira page must also surface the latest live Jira Actuals exclusions as a ticket-level correction queue. SPARC persists each excluded worklog with its Jira ticket, labor impact, raw Work Type value, Jira identity, Jira project, and unresolved reason, then groups those records by ticket for review. Missing or unrecognized Work Type is corrected on the linked Jira ticket; an unmapped Jira identity is corrected in the SPARC Jira Users mapping table; an unmapped Jira project is corrected through Product Settings. A corrected ticket enters canonical Actuals only after the next Jira Actuals sync. Syncs created before worklog-level diagnostics were introduced retain their aggregate excluded count but require one new live sync before ticket details are available.

Jira project/product mapping policy:

- Product Settings owns Jira project-to-Product mapping through `ProductJiraSpace`.
- Expected assignments such as CCTE to `CCTE`, TISA to `TISA`, RC to `RC`, and GOV/RPA to `Core Infrastructure` must be configured there; they are not hard-coded fallbacks.
- ROADMAP, PRJ, UI, APPDEV, DYNINTAKE, HB, ATO, QA, and CIS are excluded.
- Unknown Jira project keys become unmapped references requiring review.
- Unknown Jira projects must not silently map to Core Infrastructure.

Inactive Product policy:

- Inactive Products and their historical Forecast, Actual, Estimate, and audit rows remain readable for reporting.
- Inactive Products cannot receive new Forecast entries.
- Jira Actual sync, estimation, and Roadmap Product inference ignore inactive Products.
- Products with planning, labor, Roadmap, Jira, estimate, or recommendation history cannot be deleted through the API; mark them inactive instead.

Roadmap mapping ownership:

- Jira Agency Office is synchronized descriptive Roadmap metadata and is not editable in SPARC.
- Product and Bucket mappings carry `manual` or `sync` provenance.
- Manual Product/Bucket overrides survive Jira refresh.
- Clearing an override returns that field to Jira-derived inference.
- Roadmap Item Agency Office is not the Program Area authorization boundary; Product Program Area remains `Product.office`.

Work bucket normalization should inspect configurable Jira fields such as:

- Work Type
- Type of Work
- Work Category
- Development Type
- Request Type

Normalize values:

- Net New, New, New Feature, New Development -> NET_NEW
- Enhance, Enhancement, Enhance Existing -> ENHANCE
- Maintenance, Maintain, Support, Bug Fix -> MAINTENANCE
- Missing or unrecognized work type must remain unclassified and require review; do not default it to Maintenance or Net New.

## Estimation Model

SPARC estimates labor only when Jira issue/activity evidence supports it.

Rules migrated from the Annual Hourly Report estimator:

- Monthly full-capacity target defaults to 120 hours per person.
- Assignment alone is weak evidence.
- A ticket contributes estimated hours only near observable Jira movement.
- The current active window is 10 days ending on updated/resolved date.
- If a person has multiple active tickets on the same day, split that day’s capacity across them.
- Exclude no-activity statuses such as On Hold, Blocked, Cancelled, and Canceled.
- Exclude Ready for Development / To Do when no actual logged time exists.
- Project pause dates stop generating estimates after the pause date.
- Story points are optional weighting, not direct hours.
- Issue type defaults matter when story points are missing.
- Logged hours can influence effort weight, but incomplete actuals should not automatically replace estimates.
- Future months may be forecast from recent history when enabled by profile.

Estimation must store:

- Estimation profile settings.
- Estimation run history and rules snapshot.
- Monthly EstimatedEntry totals.
- EstimatedIssueAllocation audit detail explaining included/excluded issue evidence.

## Exports

SPARC should eventually export:

- Annual Hourly Report workbook.
- TimeTracking-shaped workbook/CSV for compatibility.

Exports should be generated from SPARC data, not used as the source of truth.

Unknowns to leave configurable:

- exact Rovo query syntax
- exact Jira fields for hours worked
- exact Jira field for bucket classification

## Spreadsheet Import

Initial Team Member data comes from spreadsheet import.

Expected columns:

- First Name
- Last Name
- Role
- Team
- Bill Rate
- Employment Type
- Contracting Company

Import behavior:

1. Validate required fields.
2. Create Team Members.
3. Default active status to active.
4. Generate Team Member ID if none provided.
5. Set created_at and updated_at.
6. Allow records to be edited after import.

## Testing Requirements

Backend tests:

- Fiscal year mapping
- Cost calculation
- Forecast upsert uniqueness
- Dashboard summary aggregation
- Product detail aggregation
- Bucket distribution calculation
- Jira/Rovo mock normalization
- Forecast, Actual, and Estimated coexistence at the same grain
- Reported/Effective rule selection
- Actual completeness threshold behavior
- Excluded Jira statuses
- Excluded Jira projects
- Unknown Jira projects remain unmapped
- Project pause date cutoffs
- Overlapping Jira ticket capacity splitting
- Estimation run audit snapshots
- Repeated estimation runs preserve history
- Jira project-to-Product corrections reattribute all Jira Actuals without changing Forecast or manual Actual rows
- Jira ticket-to-Roadmap corrections are fiscal-year scoped and survive later Roadmap syncs
- Attribution correction audit history captures actor, before/after values, and exact Actual impact

Frontend tests:

- Dashboard renders Product rows
- Product row click navigates to detail page
- Product Detail renders three bucket sections
- Team Member names link to Team Member Detail
- Forecast cells are editable only in Forecast Hours mode

## Do Not Build Unless Asked

- Kubernetes deployment
- Real authentication/authorization
- Role-based permissions
- Gantt/timeline/project management features
- Sprint boards
- Complex workflow approvals
- Rate versioning
- Full Jira/Rovo live integration before mock integration is complete
- Bootstrap
