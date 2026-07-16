# SPARC Build Milestones

SPARC is the internal labor forecasting and cost intelligence app for this project. This is the living milestone tracker; historical completion notes remain in the milestone bodies, while the status and active backlog below describe the application as deployed to stage on July 16, 2026.

## Current State

- MVP Planning Release: complete.
- Actuals Intelligence Release: complete for the current Jira/Roadmap scope and running in stage.
- Pilot Readiness Release: in progress.
- SPARC-local users, roles, Program Area assignments, backend authorization, redaction, and local test login are implemented.
- Entra application code is implemented; App Registration values and stage secret configuration remain external dependencies for end-to-end SSO.
- Roadmap billing milestones 1 through 5 are implemented and awaiting final stakeholder acceptance against real stage data.

## Active Backlog

1. Complete Florie's stage acceptance of the simplified Forecast Adjustment Review scope, decision lifecycle, and confirmation flow.
2. Review Team pages, especially the Product Forecast section, for correct ownership, calculations, terminology, and planning workflow.
3. Complete role-based stage acceptance for Admin, Leadership View Only, Program Area View Only, and a Program Area user with no assignments.
4. Prevent disabling or demoting the final active SPARC Admin and add the explicit no-Program-Area state.
5. Add browser-level role/login regression coverage, repair ESLint configuration, and add backend tests, migration checks, and stage smoke tests to CI.
6. Complete Roadmap billing acceptance with real gaps, remapping, sync persistence, financial-impact confirmation, audit history, summaries, exports, and forecast recommendation decisions.
7. Complete pilot runbooks, backup/restore notes, known limitations, onboarding, and repeatable stakeholder validation.
8. Configure and validate Entra SSO after DevOps supplies the external registration and secret values.

## Build Principles

- SPARC is a labor forecasting and cost intelligence app, not a project management app.
- Product is the primary planning entity.
- Manager-curated Team Member records are truth. Jira/Rovo contributors are evidence.
- Forecast hours are manually managed in SPARC.
- Actual hours are imported from app-owned Jira/Rovo codepaths.
- Cost is calculated from hours and bill rate.
- Jira/Rovo access must stay server-side and app-owned.
- UI should remain contextual, dense, and work-focused.

## Release Shape

The build is organized into three practical releases:

1. **MVP Planning Release - Complete**: reliable local app, durable schema, roster import, forecast editing, and useful dashboard/product/team views.
2. **Actuals Intelligence Release - Complete for current scope**: live Jira/Rovo path, mappings, actual hours ingestion, Roadmap attribution, sync history, and analytics rules.
3. **Pilot Readiness Release - In progress**: quality gates, operational hardening, deployment readiness, SSO configuration, and stakeholder acceptance.

## Milestone 0: Scaffold Baseline

**Status**: Complete

**Outcome**

SPARC runs locally and demonstrates the main navigation and data model.

**Completed Deliverables**

- Monorepo with `frontend/` and `backend/`.
- React + TypeScript + Vite frontend.
- Tailwind CSS and shadcn-style UI primitives.
- Recharts pie chart on Product Detail.
- TanStack Table usage for data tables.
- FastAPI backend with SQLAlchemy models.
- PostgreSQL through Docker Compose.
- Seeded Product, TeamMember, Bucket, FiscalMonth, ForecastEntry, ActualEntry, JiraUserMapping, and JiraProductMapping data.
- Seeded buckets: Net New, Enhance, Maintenance.
- FY2026 fiscal calendar from July 2025 through June 2026.
- Dashboard, Product Detail, Team Member Detail, and Team Management pages.
- Forecast upsert API and editable forecast cells.
- Mock Jira/Rovo sync service and unmapped reference APIs.

**Historical Gaps At Scaffold Completion**

These gaps were recorded at Milestone 0 and are not the current backlog. Alembic, spreadsheet import, mapping management, live Jira/Rovo integration, an image build/publish pipeline, and substantial backend test coverage now exist. Remaining CI quality-gate work is tracked under Milestone 10.

## Milestone 1: Foundation Hardening

**Status**: Implemented for MVP

**Outcome**

Make the scaffold durable enough that future feature work does not keep reshaping the ground underneath it.

**Backend Deliverables**

- Add Alembic migrations and an initial migration for the current schema.
- Add explicit database initialization commands instead of relying only on app startup side effects.
- Split seed data into repeatable seed scripts or commands.
- Add typed response schemas for the main API responses.
- Add consistent API error responses for validation, not found, and conflict cases.
- Add request logging and useful startup diagnostics.
- Add environment validation for database settings.

**Frontend Deliverables**

- Add a shared API error boundary or error display pattern.
- Add loading, empty, and error states for every route.
- Add a fiscal year constant strategy that can later become a selector.
- Add a small app configuration layer for API base URL and fiscal year defaults.

**Acceptance Criteria**

- A developer can run `docker compose up --build` from a clean checkout.
- A developer can reset and reseed the database with one documented command.
- Backend startup does not create duplicate seed data.
- All current pages still render after a database reset.
- Backend test suite includes migration/seed smoke coverage.

**Dependencies**

- Current scaffold.
- Agreement that FY2026 remains the MVP seed year.

**Risks**

- Avoid overbuilding a full platform framework too early.
- Keep migrations simple until the model stabilizes.

## Milestone 2: Durable Data Model And API Contracts

**Status**: Implemented for MVP core contracts

**Outcome**

Lock the domain model enough to support imports, mappings, analytics, and real usage.

**Backend Deliverables**

- Review and refine uniqueness constraints for forecast and actual entries.
- Add optional generated Team Member ID behavior if no source ID exists.
- Add Product and Team Member create/update validation.
- Add soft-active status handling for Products and Team Members.
- Add fields needed for Jira/Rovo scope configuration:
  - Product Jira space key
  - Product Jira project key if different from display key
  - Product active status
  - Team or workspace Jira scope metadata when the workspace/team concept is added
- Add sync metadata tables or fields:
  - sync run ID
  - source system
  - started at
  - completed at
  - status
  - imported count
  - skipped count
  - error summary
- Add source identifiers to actual entries where needed:
  - Jira issue ID
  - Jira issue key
  - worklog ID
  - worklog author account ID
  - source payload hash or equivalent idempotency key

**API Deliverables**

- Finalize response shapes for:
  - Dashboard summary
  - Product summary rows
  - Product detail summary
  - Bucket tables
  - Team member product associations
  - Unmapped Jira/Rovo users
  - Unmapped Jira/Rovo products
- Add pagination and filtering where data can grow:
  - Team members
  - Products
  - Actual entries or sync evidence
  - Unmapped references

**Acceptance Criteria**

- Forecast upserts are idempotent by Product, Team Member, Bucket, and Fiscal Month.
- Actual imports are idempotent by stable source identity, not display text.
- API contracts are documented through FastAPI schemas.
- Product and Team Member edits update timestamps consistently.

**Dependencies**

- Milestone 1.

**Risks**

- Jira issue keys can drift, so live integration must prefer stable Jira issue ID when available.
- Bill rate versioning should remain out of scope unless explicitly approved.

## Milestone 3: Spreadsheet Import And Roster Management

**Status**: Implemented for MVP

**Outcome**

Managers can bring in real team member data from spreadsheets, review it, and keep the curated roster clean.

**Backend Deliverables**

- Add CSV/XLSX import service for Team Members.
- Validate expected columns:
  - First Name
  - Last Name
  - Role
  - Team
  - Bill Rate
  - Employment Type
  - Contracting Company
- Generate Team Member ID when missing.
- Default imported Team Members to active.
- Detect likely duplicates by staff ID, name, and role/team combination.
- Support idempotent re-import.
- Return row-level validation errors.
- Maintain created and updated timestamps.

**Frontend Deliverables**

- Add Team import screen or modal from Team Management.
- Add upload, preview, validation, and confirmation steps.
- Show imported, updated, skipped, and failed row counts.
- Let managers edit bill rate and status after import.
- Keep Team Member names clickable to detail views.

**Acceptance Criteria**

- A valid spreadsheet can create multiple Team Members.
- Re-importing the same file does not create duplicates.
- Invalid rows are shown with practical error messages.
- Existing bill rates can be edited after import.
- Inactive Team Members remain visible where historical actuals or forecasts exist.

**Dependencies**

- Milestone 2 data constraints.
- Sample spreadsheet from the real business process.

**Risks**

- Spreadsheet column names may vary.
- Names alone are weak identity. Prefer staff ID where possible.

## Milestone 4: Forecast Planning Workflow

**Status**: Implemented for MVP planning workflow

**Outcome**

Product Detail becomes a practical planning surface, not just a demo matrix.

**Backend Deliverables**

- Support batch forecast upserts for matrix editing.
- Add validation for non-negative hours.
- Add optional notes or audit trail for forecast changes if stakeholders need traceability.
- Add endpoints to copy or initialize forecasts from a prior month/year if approved.
- Recalculate derived summaries after forecast changes.

**Frontend Deliverables**

- Allow editors to remove an accidentally added Product + Team Member + Bucket Forecast line when all Forecast hours are zero and no Actual labor exists, without removing Product Team membership.
- Improve forecast table editing:
  - batch save
  - save state
  - dirty cell indication
  - validation feedback
  - keyboard-friendly movement
  - revert unsaved changes
- Add mode controls for viewing:
  - Forecast Hours
  - Actual Hours
  - Forecast Cost
  - Actual Cost
  - Variance
- Add totals that remain visible while horizontally scrolling.
- Add a fiscal year selector when more than one year exists.
- Add export to CSV for Product Detail tables if stakeholders need offline review.

**Acceptance Criteria**

- Forecast Hours are editable.
- Actual Hours are read-only.
- Cost and variance are read-only calculated values.
- Team Member links navigate to Team Member Detail.
- Saving multiple edits is reliable and visibly confirmed.
- Product totals update after saving.

**Dependencies**

- Milestone 2 API contracts.
- Product owner confirmation on whether copy-forward is in scope.

**Risks**

- Large matrix tables can become hard to use. Keep interactions dense but restrained.
- Per-cell saves are simple but can feel slow. Batch save is likely better for real planning.

## Milestone 5: Mock Jira/Rovo Actuals And Mapping Workflow

**Status**: Implemented for MVP mock integration

**Outcome**

The app proves the actual-hours model with realistic mock ticket/worklog evidence before live external integration.

**Backend Deliverables**

- Expand mock Jira/Rovo data to resemble ticket-level actuals:
  - issue ID
  - issue key
  - project key
  - summary
  - status
  - bucket signal
  - worklog author
  - worklog date
  - worklog hours
- Normalize worklog dates into FiscalMonth records.
- Map Jira users to Team Members.
- Map Jira projects/spaces to Products.
- Store unmapped users and products.
- Split actual time into:
  - curated team-member time
  - external or unmapped contributor time
  - total Jira/Rovo time
- Add sync run history.

**Frontend Deliverables**

- Add a Jira/Rovo sync panel or route.
- Show sync readiness for mock mode.
- Show latest sync status.
- Show unmapped Jira users and Jira products.
- Add mapping management UI:
  - map Jira user to Team Member
  - map Jira project/product to Product
  - mark external contributor if needed
- Add resync behavior after mappings are created.

**Acceptance Criteria**

- Mock sync imports actual hours idempotently.
- Unmapped users/products are visible.
- Creating a mapping and re-running sync moves hours into the correct Product and Team Member.
- External/unmapped time does not pollute curated team-only analytics.

**Dependencies**

- Milestone 2 sync metadata.
- Milestone 3 roster import.

**Risks**

- Bucket classification may be incomplete. Make unknown bucket behavior explicit.
- External contributor time must be visible without being treated as curated staff effort.

## Milestone 6: App-Owned Live Jira/Rovo Integration

**Status**: Complete for current stage scope

**Outcome**

SPARC can fetch actual hours from Jira/Rovo through controlled server-side integration.

**Security Pattern**

- The app owns Jira/Rovo access.
- Jira/Rovo credentials live only in server environment variables.
- Jira/Rovo scope is stored in app data.
- Server code makes all external calls.
- The AI only works through SPARC codepaths like `run sync`.
- No arbitrary direct Jira API calls from prompts, tools, or client code.

**Backend Deliverables**

- Add server-side integration configuration:
  - `JIRA_API_EMAIL`
  - `JIRA_API_TOKEN`
  - Jira site URL
  - Jira scope JQL or Rovo query configuration
  - Jira board/team/product scope fields as needed
- Add readiness checks:
  - credentials present
  - scope configured
  - mappings available or unmapped reporting ready
- Build live fetch service:
  - paginated Jira/Rovo issue search
  - worklog follow-up fetches when embedded worklogs are truncated
  - configurable field mapping for sprint/bucket/story point fields if needed later
- Normalize live payloads into internal snapshot format before import.
- Import by stable Jira issue ID first, Jira key second.
- Record sync run status and source payload errors.
- Add rate-limit and retry handling.

**Frontend Deliverables**

- Add integration settings UI once configuration is ready to be managed in-app.
- Add readiness state and sync controls.
- Add sync result details:
  - fetched issues
  - imported worklogs
  - skipped worklogs
  - unmapped references
  - errors

**Acceptance Criteria**

- No Jira/Rovo credential is exposed in browser code or API responses.
- Live sync can run through one server-owned endpoint.
- Jira/Rovo payloads are normalized before import.
- Imports remain idempotent.
- Unmapped users/products are surfaced without breaking sync.

**Dependencies**

- Milestone 5 mapping workflow.
- Real Jira/Rovo access details and allowed scope.
- Product owner decision on where Jira scope lives: Product, Team, Workspace, or all three.

**Risks**

- Rovo query syntax and available fields may differ from assumptions.
- Jira custom field IDs may vary by site.
- Worklogs can be large or truncated.

## Milestone 7: Derived Analytics And Business Rules

**Status**: Complete for current product scope

**Outcome**

The UI is driven by SPARC-owned analytics, not raw Jira/Rovo payloads.

**Backend Deliverables**

- Add analytics service layer for:
  - dashboard summary
  - product summary
  - product bucket distribution
  - product monthly matrix
  - team member inverse view
  - team-only vs external actual hours
  - remaining forecast
  - variance
- Add derived stats tables if runtime aggregation becomes slow.
- Define business rules for:
  - inactive Team Members
  - inactive Products
  - unmapped contributors
  - unknown buckets
  - canceled/pre-resolved Jira work if live Jira status hygiene matters
- Add tests for aggregation correctness.

**Frontend Deliverables**

- Add dashboard trend indicators where useful.
- Add Product Detail variance views.
- Add Team Member Detail totals and product association clarity.
- Add explanations through labels and concise table headings, not instructional walls of text.

**Acceptance Criteria**

- Dashboard metrics reconcile with Product Detail totals.
- Product Detail totals reconcile with bucket tables.
- Team Member Detail totals reconcile with Product Detail rows.
- Team-only actuals can be separated from external actuals.
- Cost values are always calculated, never manually edited.

**Dependencies**

- Milestones 4 through 6.

**Risks**

- Stakeholders may disagree on variance semantics. Confirm whether variance means actual minus forecast or forecast minus actual and keep it consistent.
- Current bill rate calculations are MVP-only. Do not introduce rate versioning without approval.

## Milestone 8: Product And Team Management Completion

**Status**: Complete for current product scope

**Outcome**

Managers can maintain the operational reference data needed for forecasting.

**Backend Deliverables**

- Complete Product CRUD.
- Complete Team Member CRUD.
- Add status transitions or simple active/inactive updates.
- Add validation for bill rate, employment type, contracting company, and required fields.
- Add optional Product description and Jira reference fields.

**Frontend Deliverables**

- Add Product management entry point if stakeholders need direct Product maintenance.
- Expand Team Management inline editing beyond bill rate if approved:
  - role
  - team
  - employment type
  - contracting company
  - status
- Add confirmation for status changes that affect active planning.
- Add filters for active/inactive and team.
- Add table search.

**Acceptance Criteria**

- Managers can keep roster and product records current without database access.
- Inactive records do not disappear from historical views.
- Inline edits are clear, saved, and reversible before commit where practical.

**Dependencies**

- Milestone 3 import.
- Product owner decision on whether Product management belongs in MVP.

**Risks**

- Too much inline editing can make tables noisy. Keep controls focused on high-frequency edits.

## Milestone 9: UX Polish And Accessibility

**Status**: Ongoing

**Outcome**

SPARC feels like a real internal tool: dense, clear, fast, and hard to misuse.

**Frontend Deliverables**

- Review all pages for responsive behavior.
- Improve matrix scrolling and sticky labels.
- Add accessible labels for every editable control.
- Add keyboard workflows for tables.
- Add visible save, success, and error states.
- Add empty states for no forecasts, no actuals, and unmapped references.
- Add consistent number formatting for hours, dollars, and percentages.
- Add chart colors and legends that remain understandable without relying only on color.
- Keep persistent navigation minimal.

**Acceptance Criteria**

- Dashboard is readable on laptop and large desktop.
- Product matrices remain usable at realistic widths.
- Forecast cells are uniquely accessible by label.
- Text does not overlap or clip in core pages.
- Product and Team Member links are available wherever names appear.

**Dependencies**

- Main workflows are implemented.

**Risks**

- Dense analytical pages can become visually heavy. Prioritize scanability over decoration.

## Milestone 10: Testing, CI, And Quality Gates

**Status**: Partially complete

The backend suite, migration checks used during releases, frontend TypeScript production build, and Docker image build/publish workflow exist. Missing quality gates are browser-level role/workflow tests, a working ESLint 9 configuration, backend test and migration jobs in GitHub Actions, and a post-rollout stage smoke test.

**Outcome**

The team can change SPARC without guessing whether core planning math still works.

**Backend Tests**

- Fiscal year mapping.
- Cost calculation.
- Forecast upsert uniqueness.
- Dashboard summary aggregation.
- Product detail aggregation.
- Team member inverse aggregation.
- Bucket distribution.
- Spreadsheet import validation.
- Mock Jira/Rovo normalization.
- Mapping workflow.
- Live Jira/Rovo import using recorded fixtures when available.

**Frontend Tests**

- Dashboard renders product rows.
- Product row links navigate to Product Detail.
- Product Detail renders all three bucket sections.
- Forecast cells are editable and actual/cost/variance cells are read-only.
- Team Member names link to Team Member Detail.
- Team Management bill rate edits save.
- Unmapped user/product workflow renders.

**End-To-End Tests**

- Clean reference-only database seed.
- Dashboard smoke test.
- Forecast edit and totals update.
- Team import and bill rate edit.
- Mock sync and mapping.

**CI Deliverables**

- Backend test job.
- Frontend typecheck/build job.
- Linting or formatting checks.
- Docker build smoke test.
- Container image build and publish for STAGE.
- Pipeline hook for database migrations.
- STAGE deployment smoke test after Kubernetes rollout.

**Acceptance Criteria**

- CI runs on every pull request.
- Core aggregation tests use deterministic fixtures.
- A failed forecast or actuals calculation blocks merge.
- STAGE images are only published after required checks pass.

**Dependencies**

- Stable contracts from earlier milestones.

**Risks**

- E2E tests can become brittle if added before workflows settle. Start with high-value smoke tests.

## Milestone 11: Pilot Readiness And Operations

**Status**: In progress

Stage is deployed as a container against Azure PostgreSQL with health endpoints, scheduled Jira sync, and immutable build-version verification. Remaining work includes operational and backup/restore runbooks, pilot/onboarding material, stronger automated stage validation, and external Entra registration/secret configuration.

**Outcome**

SPARC is ready for a controlled pilot with real users and real data.

**Operational Deliverables**

- Deploy STAGE as containerized workloads on the Kubernetes cluster.
- Use Azure PostgreSQL for STAGE data storage.
- Pull secrets from Azure Key Vault, either through app-owned retrieval or environment injection at startup.
- Document the agreed secret pattern before live Jira/Rovo credentials are added.
- Add Kubernetes deployment handoff artifacts or manifests, depending on DevOps ownership.
- Add production configuration documentation.
- Add database backup and restore notes.
- Add health checks.
- Add structured logging for imports and sync runs.
- Add a basic admin/runbook document.
- Add data reset and seed strategy for non-production environments.
- Add security review notes for Jira/Rovo credentials.

**Product Deliverables**

- Pilot checklist.
- Known limitations list.
- First-user onboarding notes.
- Feedback capture plan.
- Demo script for Dashboard, Product Detail, Team Detail, Team Management, import, and sync.

**Acceptance Criteria**

- A pilot user can complete the happy path with realistic data:
  - import roster
  - review products
  - enter forecast
  - run actuals sync
  - map unmapped references
  - review dashboard and detail pages
- The engineering team can diagnose failed syncs.
- Credentials are not exposed to the client.
- Known limitations are documented before pilot.
- STAGE frontend can reach STAGE backend.
- STAGE backend can connect to Azure PostgreSQL.
- STAGE backend receives required secrets through the agreed Key Vault path.

**Dependencies**

- Milestones 1 through 10.
- SPARC-local authorization is implemented. End-to-end Entra SSO depends on external App Registration values and stage secret configuration.
- DevOps confirmation of registry, namespace, ingress/host, and Key Vault integration pattern.

**Risks**

- Production deployment and authentication requirements may reshape the app boundary.
- Real Jira/Rovo data may reveal identity and bucket edge cases not covered by mock data.
- App-owned Key Vault retrieval may require managed identity or cluster-level setup outside the app repo.

## Cross-Cutting Decisions And Current State

These decisions were raised during the original build plan; the table records their current resolution or deferral.

| Decision | Current State |
|---|---|
| Jira/Rovo Product scope | `ProductJiraSpace` is the canonical Jira project-to-Product mapping. |
| Product maintenance | Implemented in Product Settings with history-safe inactive/delete behavior. |
| Forecast save behavior | Batch save/discard workflow is implemented. |
| Fiscal years | Fiscal-year selection is implemented; stage currently plans against configured years including FY2027. |
| Bill rate history | Explicitly deferred until requested. |
| Authentication and authorization | Local test authentication and SPARC authorization are implemented; Entra configuration is externally pending. |
| Jira Bucket classification | Recognized values map explicitly; missing or unknown work types remain unclassified and are not silently defaulted. |
| Stage secrets | Environment/secret injection is in use; Entra values remain pending from DevOps. |
| Deployment ownership | GitHub builds/pushes the image and the stage platform rolls it out; infrastructure manifests remain outside the current app work. |

## Active Execution Order

1. Non-Entra access hardening and automated role-flow coverage.
2. Roadmap billing stage acceptance and real-data gap cleanup.
3. CI quality gates and deployment smoke testing.
4. Pilot operations and stakeholder handoff material.
5. Entra end-to-end validation when external registration values are available.

Do not restart completed foundation, mock integration, live Jira, authorization, or Roadmap implementation milestones unless stage evidence identifies a specific defect.
