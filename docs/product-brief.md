# SPARK Product Brief

SPARK means Staff Planning & Resource Knowledge.

## Project Purpose

Build an internal labor forecasting and cost intelligence web app for a State Department of Education IT team.

This is not a project management tool. Do not add task boards, sprint planning, timeline management, due dates, or Gantt charts unless explicitly requested.

## Canonical Terms

- Use Product, not Project, as the primary work entity.
- Every Product maps to a Jira space.
- Use Team Member for people/labor resources.
- Use Bucket for work type: Net New, Enhance, Maintenance.
- Forecast hours are manually entered in this app.
- Actual hours come from Jira/Rovo API.
- Cost is calculated as hours multiplied by bill rate.
- Product budget is stored on the Product record.
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
- Products and Team Members must be clickable wherever they appear.
- Dashboard summarizes Products.
- Product Detail is the main analytical page.
- Team Member Detail shows the inverse view across Products.
- Keep tables data-dense but readable.
- Do not create a large traditional nav menu unless explicitly requested.

## Data Rules

- Fiscal year runs July through June.
- Forecast hours are editable.
- Actual hours are read-only from Jira/Rovo.
- Cost values are calculated, not manually entered.
- Bill rate can be updated after spreadsheet import.
- MVP uses current bill rate for calculations.
- Future state may add bill rate versioning.
- Budget tracker compares projected spend against budget using a compact horizontal consumed-vs-remaining bar.
- Team Member ID is optional and system-generated if not provided.
- Team Members default to active.
- Created date and last updated date are required.

## Product Buckets

Each Product has three buckets:

1. Net New
2. Enhance
3. Maintenance

Product Detail pages must organize detailed labor data by these buckets.

## Required Pages

Build these primary routes:

- `/` — Dashboard
- `/products/:productId` — Product Detail
- `/team-members/:teamMemberId` — Team Member Detail
- `/team` — Team Management

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

1. Product header
   - Product name
   - Jira space key/reference
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
   - Shows Product projected spend against Product budget

6. Three Product-specific data sections:
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
- Variance cells are read-only calculated values.

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

3. Budget Tracker
   - Shows Team Member projected spend against the combined budgets of Products they support

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

Team Management should be an editable table.

Columns:

- Name
- Role
- Team
- Bill Rate
- Employment Type
- Contracting Company
- Status
- Last Updated

Rules:

- Inline editing preferred.
- Name links to Team Member Detail page.
- Active status defaults to active.
- Bill rates can be updated after import.
- Rate changes affect future forecasting calculations.
- Created date and updated date are maintained by the backend.

## Backend Requirements

Use FastAPI.

Do not put business logic directly in route handlers.

Use service modules for:

- cost calculations
- dashboard aggregation
- fiscal year logic
- Jira/Rovo normalization
- forecast upserts

## Database Entities

Implement:

- Product
- TeamMember
- Bucket
- FiscalMonth
- ForecastEntry
- ActualEntry
- JiraUserMapping
- JiraProductMapping

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

Team Members:

- `GET /api/team-members`
- `POST /api/team-members`
- `GET /api/team-members/{team_member_id}`
- `PUT /api/team-members/{team_member_id}`
- `GET /api/team-members/{team_member_id}/products?fiscal_year=2026`

Forecasts:

- `GET /api/forecasts?product_id=&team_member_id=&fiscal_year=`
- `PUT /api/forecasts`

Jira/Rovo:

- `POST /api/integrations/jira-rovo/sync`
- `GET /api/integrations/jira-rovo/unmapped-users`
- `GET /api/integrations/jira-rovo/unmapped-products`

## Jira/Rovo Integration

Actual hours come from Jira through the Rovo API interface.

MVP should mock this integration.

The app should eventually:

1. Query Jira ticket/worklog data through Rovo API.
2. Extract hours worked from Jira fields.
3. Identify Jira user.
4. Identify Jira space/Product.
5. Identify bucket if Jira has bucket/type data.
6. Normalize worklog dates into fiscal months.
7. Store actual hours.
8. Surface unmapped users/products.

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
