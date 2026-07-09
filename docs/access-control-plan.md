# SPARC Access Control Plan

SPARC uses Microsoft Entra for authentication and SPARC-owned data for authorization.

This plan intentionally keeps access control independent from Jira roadmap metadata. Program Area visibility is based on SPARC Product ownership, not roadmap item fields, Jira agency office fields, Team Member teams, or Team Member labor roles.

## Source Of Truth

- Product Program Area is stored today as `Product.office`.
- User-facing labels should say Program Area where this value is used for reporting or access.
- `Product.division` is lower-level organization metadata for filtering/reporting and is not the initial security boundary.
- `RoadmapItem.program_area` is source/display metadata only. It must not be used for role checks, data scoping, authorization decisions, or restricted exports.
- A Product with no Program Area remains visible to Admin and Leadership View Only users, but not to Program Area View Only users.

## Roles

### Admin

- Can view all Products, Team Members, Forecasts, Actuals, Reports, Admin pages, and exports.
- Can edit Products, Team Members, Forecasts, Jira mappings, imports, syncs, and user access.
- Can see hours, costs, and bill rates.
- The existing `sparc` login remains a break-glass Admin login while SSO is built and tested.

### Leadership View Only

- Can view all Program Areas.
- Cannot edit.
- Can see hours and costs.
- Cannot see bill rates.
- Cannot run admin-only operations such as sync, import, system scan, or user access changes.

### Program Area View Only

- Can view only Products where `Product.office` matches one of the user's assigned Program Areas.
- Can be assigned multiple Program Areas.
- Cannot edit.
- Cannot see bill rates.
- If assigned no Program Areas, receives no scoped SPARC data and should see a clear "No Program Area assigned" state.
- Initial implementation should avoid named Team Member detail for this role unless product leadership explicitly approves it.

## Identity Model

SPARC users are app users, not Team Members. A user may also be a Team Member in real life, but access control does not depend on Team Member records.

User records should include:

- email
- display name
- role
- active/inactive status
- local password hash for pre-SSO testing
- local login enabled flag
- Entra tenant ID, when linked
- Entra object ID, when linked
- last login timestamp

Before SSO is available, real users can log in with their email address and temporary local password. After SSO is available, the same user record is linked to Entra on first successful SSO login. Email can be used for first-time linking, but future matching should prefer Entra tenant ID plus object ID.

## Program Area Assignments

Program Area assignments are many-to-many:

- one user can have many Program Areas
- one Program Area can have many users

Assignments should validate against configured Product Program Area values. The current configured values are:

- Academics
- Operations
- Programs
- Deputy Commissioner
- Commissioners Office
- General Counsel

## Backend Enforcement

Backend enforcement is mandatory. UI hiding is not security.

Every API or export returning Products, Forecasts, Actuals, Team Members, Reports, dashboard values, roadmap actuals, or admin data must apply the current user's role and scope before returning data.

Restricted users must not be able to retrieve bill rates from direct API calls, XLSX exports, or admin data exports.

For Program Area View Only users, scoping must be based on:

```text
Product.office IN current_user.assigned_program_areas
```

If a roadmap endpoint is later made available to scoped users, it must scope through the mapped Product first:

```text
Roadmap Item -> Product -> Product.office
```

It must not scope by `RoadmapItem.program_area`.

## Milestones

### Milestone 0: Access Readiness Fence

- Document `Product.office` as the Program Area source of truth.
- Document `RoadmapItem.program_area` as non-authoritative metadata for authorization.
- Confirm blank Program Area behavior.
- Keep Roadmap Item cleanup out of the role implementation path.

### Milestone 1: Local User Data Model

- Add SPARC-local user table.
- Add many-to-many Program Area assignment table.
- Add role constants and capability helpers.
- Preserve existing Product, Team Member, Forecast, Actual, and Jira mapping tables.

### Milestone 2: Break-Glass Admin Preservation

- Keep the existing `sparc` credentials working.
- Resolve `sparc` to an Admin capability set.
- Prevent disabling or demoting the final active Admin once user management exists.

### Milestone 3: Email-Based Local Login

- Let Admin-created users log in with email plus temporary password before SSO.
- Store password hashes only.
- Allow local login to be disabled per user after SSO is in place.

### Milestone 4: Admin User Management API

- List users.
- Create users.
- Update user role, display name, email, active status, and local login setting.
- Assign and remove multiple Program Areas.
- Set or reset temporary passwords.
- Restrict the API to Admin users.

### Milestone 5: Auth Status Capabilities

- Return authenticated user identity.
- Return role.
- Return assigned Program Areas.
- Return capabilities such as `can_admin`, `can_edit_forecast`, `can_run_sync`, `can_view_rates`, `can_view_costs`, `can_view_hours`, and `can_view_named_people`.

### Milestone 6: Backend Permission And Scope Enforcement

- Add `current_user`, `require_admin`, `require_write_access`, and Program Area scoping helpers.
- Apply scoping to dashboard, Products, Product Detail, Forecasts, Actuals, Team Members, Reports, and exports.
- Ensure no-area Program Area users receive no scoped data.

### Milestone 7: Redaction

- Remove bill rates from restricted API responses.
- Remove bill rates from restricted exports.
- Add tests proving restricted users cannot retrieve rates.

### Milestone 8: Admin Access UI

- Add an Admin Users tab.
- Support create/edit users.
- Support role selection.
- Support multi-Program-Area assignment.
- Support temporary password/reset workflow.
- Show local login and SSO linked status.

### Milestone 9: Role-Specific Frontend Behavior

- Hide or disable edit controls for read-only roles.
- Hide Admin navigation for non-admins.
- Show no-assigned-Program-Area state.
- Bump the frontend/interface version for each interface change.

### Milestone 10: Entra SSO

- Add Entra authorization-code callback.
- Match by Entra tenant/object ID when linked.
- Match by active SPARC user email on first SSO login.
- Store Entra tenant/object ID after first successful match.
- Keep `sparc` break-glass login available for stage.
