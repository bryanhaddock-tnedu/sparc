# SPARC Product Update - July 14, 2026

## Summary

SPARC has made meaningful progress toward production-ready access control, Program Area visibility, stage validation, and budget reporting. The major shift is that SPARC now has its own user/role model and backend-enforced data scoping, while Entra remains the planned authentication provider.

In plain terms: users can be created in SPARC, assigned roles, assigned one or more Program Areas, and given temporary local passwords before SSO is ready. Once Entra SSO is configured, those same user records can be used for SSO sign-in.

## What Is Now In Place

### 1. SPARC-Owned User Roles

SPARC now supports the three initial access roles:

- **Admin**
  - Can view and edit everything.
  - Can see hours, costs, and bill rates.
  - Can access admin tools, sync/import/config functions, and user management.

- **Leadership View Only**
  - Can view all Program Areas.
  - Cannot edit.
  - Can see hours and costs.
  - Cannot see bill rates.

- **Program Area View Only**
  - Can view only assigned Program Area Products.
  - Cannot edit.
  - Cannot see bill rates.
  - Cannot see Enterprise Reports.
  - Cannot see dashboard hour quantities.
  - Can see scoped dashboard cost context.

### 2. Program Area Mapping

Program Area access is based on the Product's Program Area value, currently stored in SPARC as `Product.office`.

Current rule:

```text
Program Area View Only user can see Product if Product.office is assigned to that user.
```

This keeps access control tied to SPARC-owned Product data rather than Jira roadmap metadata.

Important clarification:

- `Product.office` is the current Program Area security boundary.
- `RoadmapItem.program_area` may be useful metadata later, but it is not the access-control boundary.

### 3. User Management Before SSO

Admins can create SPARC users now, before Entra SSO is fully connected.

The practical flow is:

1. Admin creates user in SPARC by email.
2. Admin assigns role.
3. Admin assigns Program Area(s), if applicable.
4. Admin gives user a temporary local password.
5. User can log in and test role behavior on stage.
6. Later, when Entra SSO is configured, the same user record can link to SSO by email/Entra identity.

The existing `sparc` account remains available as a break-glass Admin login.

### 4. Entra SSO Readiness

SPARC has the application-side Entra SSO plumbing in place:

- OAuth2/OpenID Connect authorization-code callback support.
- Secure SPARC session creation after Entra login.
- Existing SPARC user matching by Entra tenant/object ID or first-time email match.
- Frontend SSO button when Entra is configured.

What is still needed:

- TDOE Entra App Registration details.
- Tenant ID.
- Client/Application ID.
- Client secret or certificate reference.
- Stage secret configuration.

Important: SPARC does not need Entra app roles for the current design. Entra authenticates; SPARC manages roles and Program Area authorization locally.

### 5. Backend-Enforced Security

Access rules are enforced in the backend, not just hidden in the UI.

Examples:

- Program Area users only receive Products for assigned Program Areas.
- Program Area users cannot request Enterprise Reports through the UI or API.
- Program Area users do not receive dashboard hour values from the API.
- Named Team Member forecast detail is blocked for roles that should not see named people.
- Bill rates are redacted for users who should not see rates.

This matters because it prevents restricted users from getting sensitive data through direct API calls or exports.

### 6. Dashboard Behavior For Program Area Users

Program Area View Only users now get a scoped dashboard:

- Products are filtered to assigned Program Area(s).
- Reports tab is hidden.
- Forecast Hrs and Actual Hrs are removed from Product Summary.
- Hour summary cards are hidden.
- Hour ranking controls are hidden.
- Dashboard mix/ranking views use cost mode where hour mode would otherwise reveal restricted quantities.

Florie validated that Academics scoping was working on stage; the latest update addresses her feedback that Reports should be hidden and dashboard hours should be removed for Program Area users.

### 7. Labor Cost Report Improvements

The Labor Cost Report now better supports budget conversations.

Added dimensions:

- Team Member Role
- Employment Type

The default report layout is now:

```text
Product > Bucket > Role > Employment Type
```

This supports Vijay's requested extract:

```text
Product | Bucket | Role | Employment Type | Forecast Hours | Forecast Cost
```

The report still includes actuals and variance columns where permitted, and XLSX export uses the selected dimensions.

Terminology note:

- **Role** in Reports means Team Member labor role.
- **User Role** or **Access Role** means SPARC permissions.

### 8. Jira Work-Type Classification Safety

SPARC no longer silently classifies unknown Jira work type values.

Current behavior:

- Missing or unrecognized Jira work type stays unclassified.
- Unclassified Jira worklogs are skipped from actuals import.
- Estimation excludes unclassified issues with a clear reason.
- SPARC does not default unknown Jira work to Maintenance or Net New.

This prevents misleading cost/bucket reporting when Jira does not provide a trustworthy work-type value.

## Milestones Completed

### Completed: Local Access Model

- SPARC app users.
- Roles.
- Program Area assignments.
- Multiple Program Areas per user.
- Local temporary-password login for pre-SSO testing.
- Break-glass `sparc` Admin preserved.

### Completed: Role-Aware UI

- Admin-only areas hidden from non-admins.
- Team/named-person areas hidden from roles without named-person access.
- Reports hidden from Program Area View Only.
- Dashboard adapts based on hour visibility.

### Completed: Backend Access Enforcement

- Program Area scope applied backend-side.
- Named Team Member forecast detail protected.
- Reports protected.
- Dashboard hours redacted.
- Bill rates redacted for restricted roles.

### Completed: Report Enhancements

- Team Member Role added as a report dimension.
- Employment Type added as a report dimension.
- Four report grouping dimensions supported.
- XLSX export updated.

### Completed: Entra Integration Readiness

- SPARC code is ready for Entra SSO configuration.
- App Registration values are the remaining dependency.
- SPARC will continue to manage roles and Program Area access locally.

### Completed: Jira Classification Hardening

- Unknown Jira work type no longer defaults to a bucket.
- Unclassified work is excluded/skipped rather than miscategorized.

## Stage Validation Checklist

For an **Admin** user:

- Can log in with `sparc`.
- Can access Admin tools.
- Can create users.
- Can assign roles and Program Areas.
- Can view Reports.
- Can see hours, costs, and bill rates.

For a **Program Area View Only - Academics** user:

- Can log in with email and temporary password.
- Sees only Academics-scoped Products on Dashboard.
- Does not see Reports navigation.
- Direct `/reports` access is blocked.
- Product Summary does not show Forecast Hrs or Actual Hrs.
- Dashboard still shows cost-oriented scoped Product information.
- Does not see bill rates.
- Does not see named Team Member detail.

For a **Leadership View Only** user:

- Can view all Program Areas.
- Can see hours and costs.
- Cannot edit.
- Cannot see bill rates.
- Cannot access Admin tools.

## Open Decisions / Follow-Up

### Entra SSO Configuration

Still pending:

- Entra App Registration.
- Stage secret configuration.
- End-to-end SSO validation.

### Product Detail For Program Area Users

Dashboard behavior has been adjusted for Program Area users. Product Detail should be reviewed next to decide whether Program Area users should:

- be blocked from Product Detail,
- see a cost-only Product Detail view, or
- see Product Detail with additional hour redaction.

### Employment Type Labeling

The report currently uses the existing Team Member Employment Type values. If leadership wants to display `FTE` instead of `Employee`, that should be a separate explicit normalization decision.

### Unclassified Jira Work Review

Unknown Jira work type is now safely excluded. A future enhancement could add an admin review queue to classify unknown Jira work types.

## Suggested Message To Share

SPARC now has the foundation for production-style user access. We can create users directly in SPARC, assign Admin, Leadership View Only, or Program Area View Only roles, and assign one or more Program Areas. Program Area users are scoped by Product Program Area, cannot access Enterprise Reports, and no longer see dashboard hour quantities. The Labor Cost Report also now supports Product, Bucket, Role, and Employment Type for budget extracts. Entra SSO plumbing is ready in the app, with App Registration/secret configuration still needed before end-to-end SSO testing.
