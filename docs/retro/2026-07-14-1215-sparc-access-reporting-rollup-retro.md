# SPARC Retrospective - 2026-07-14 12:15

## Retrospective Metadata

- Date: 2026-07-14
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Consolidated access-control, Program Area, Reports, and stage-validation rollup
- Participants: Bryan Haddock and Codex acting as SPARC engineering partner
- Branch: `develop`
- Latest commit at time of retro: `ba02526 Restrict program area reports and dashboard hours`
- Related granular retros:
  - `docs/retro/2026-07-09-1657-sparc-entra-sso-milestone-retro.md`
  - `docs/retro/2026-07-09-1720-sparc-access-hardening-retro.md`
  - `docs/retro/2026-07-10-1052-sparc-jira-bucket-classification-retro.md`
  - `docs/retro/2026-07-10-1315-sparc-report-employment-type-retro.md`
  - `docs/retro/2026-07-10-1452-sparc-program-area-dashboard-redaction-retro.md`
- Related commits:
  - `3d516ad Add local access roles and program area scoping`
  - `755a29b Apply role-aware frontend access behavior`
  - `6e45cba Add team member role report dimension`
  - `bf3b842 Add Entra SSO authentication plumbing`
  - `9a105cf Harden access control for forecast details`
  - `66d889e Stop defaulting unknown Jira work type`
  - `9d23bb9 Add employment type report dimension`
  - `ba02526 Restrict program area reports and dashboard hours`
- Handoff target: Future SPARC Codex agents, Bryan, Florie, Vijay, and DevOps

## Executive Summary

This work moved SPARC from basic username/password protection toward a real production access model. SPARC now has local app users, roles, Program Area assignments, backend data scoping, redaction rules, role-aware frontend behavior, Entra SSO plumbing, and improved report dimensions for budget conversations.

The most important architecture decision is stable: **Entra authenticates only; SPARC authorizes locally.** Program Area visibility is based on SPARC-owned Product Program Area, currently stored as `Product.office`. Jira roadmap metadata such as `RoadmapItem.program_area` must not be used as a security boundary.

## Product Decisions Captured

- Program Area and Product `office` are the same business concept for access purposes.
- User-facing language should move toward "Program Area" even if the database column remains `Product.office` for now.
- Program Area View Only users can be assigned one or more Program Areas.
- Program Area View Only users see only Products where `Product.office` is assigned to them.
- Program Area View Only users should not see Enterprise Reports.
- Program Area View Only users should not see dashboard hour quantities.
- Program Area View Only users may still see scoped dashboard cost values.
- Program Area View Only users should not see named Team Member detail unless product leadership explicitly changes that decision.
- Admin and Leadership View Only can view all Program Areas.
- Leadership View Only can view hours and costs, but not bill rates.
- Admin can view and edit everything, including bill rates and admin/sync/import/config tools.
- The existing `sparc` login remains a break-glass Admin account.
- SPARC users are app users, not Team Members.
- Team Member Role and SPARC User Role are separate concepts.
- Team Member Employment Type belongs to Team Member and is a valid Labor Cost Report dimension.
- SPARC should not combine Role and Employment Type in the report; separate fields are better for pivoting/export.
- Unknown Jira work type must remain unclassified; SPARC must not silently default it to Maintenance or Net New.

## Completed Work

### 1. Local SPARC User And Role Model

SPARC now has local authorization concepts that do not depend on Entra roles:

- `Admin`
- `Leadership View Only`
- `Program Area View Only`

The implementation supports:

- App-created users.
- Email-based login with temporary local passwords before SSO is available.
- Local password hashes rather than plaintext passwords.
- Active/inactive user state.
- Local login enabled/disabled flag.
- Entra tenant/object ID fields for SSO linking.
- Program Area assignment records.
- Multiple Program Areas per user.
- Role capabilities returned by auth status.

The Admin UI can create and update users, assign roles, assign Program Areas, and manage local-login settings.

### 2. Break-Glass Admin Preservation

The existing `sparc` credentials still resolve to Admin permissions. This remains important because:

- SSO is not fully configured yet.
- Bryan needs reliable access during stage validation.
- User setup can continue before Entra App Registration values are available.

Future agents must preserve this unless Bryan explicitly says otherwise.

### 3. Entra SSO Plumbing

SPARC now has config-gated Entra authorization-code login support:

- Login route redirects to Microsoft when Entra settings are configured.
- Callback route verifies signed state.
- ID token validation uses Microsoft JWKS.
- Existing active SPARC users can link by Entra tenant/object ID.
- First-time SSO linking can match by email.
- SPARC creates its own app session after Entra authentication.
- The React frontend does not store Entra tokens.
- No Microsoft Graph application permissions are required for the current design.
- No Entra app roles are needed for the current design.

Pending external dependency:

- Stage still needs TDOE Entra App Registration values and secret/certificate configuration before full SSO can be validated end to end.

### 4. Backend Enforcement And Redaction

Access control is enforced in the backend, not just hidden in React.

Implemented or reinforced:

- Program Area scoping through `Product.office`.
- Program Area users cannot retrieve out-of-scope Products.
- Program Area users cannot retrieve named forecast detail rows.
- Team Member bill rates are redacted for roles without rate access.
- Reports require `can_view_reports`.
- Program Area View Only has `can_view_reports = false`.
- Dashboard hour values are redacted server-side for roles without `can_view_hours`.
- Program Area dashboard hour fields return `None` / `null`, not zeros.
- Frontend hides hour cards, hour table columns, hour sort options, and hour ranking controls for roles without hour access.

Important backend principle:

- UI hiding alone is not acceptable for restricted data. If a value is not allowed, the API must not return it.

### 5. Program Area Dashboard Behavior

Program Area View Only users now get a scoped dashboard experience:

- Only assigned Program Area Products appear.
- Dashboard cost values can remain visible.
- Forecast/actual hour quantities are hidden and redacted from payloads.
- Reports tab is hidden.
- Direct `/reports` navigation is blocked.
- Reports API/XLSX export is blocked.

Florie validated that Program Area product scoping sorted correctly for Academics. Her feedback drove the final Reports hiding and dashboard-hours removal.

### 6. Labor Cost Report Improvements

The Enterprise Reports Labor Cost Report now supports the budget-oriented extract Vijay requested.

Completed report dimensions:

- Person
- Role
- Employment Type
- Team
- Product
- Bucket

Important report behavior:

- The report supports four selected grouping dimensions.
- Default report layout is Product > Bucket > Role > Employment Type.
- XLSX export includes selected dimensions.
- Team Member Role comes from `TeamMember.role`.
- Employment Type comes from `TeamMember.employment_type`.
- Report concepts are intentionally separate from SPARC access roles.

### 7. Jira Bucket Classification Hardening

SPARC no longer silently maps missing or unknown Jira work type to Maintenance.

Current behavior:

- Unknown Jira work type stays unclassified.
- Live Jira actual sync skips unclassified worklogs.
- If a previously imported actual later becomes unclassified, sync deletes the stale classified actual.
- Estimation excludes unclassified issues with a clear reason.
- Product brief documents that unknown work type requires review.

Important concept:

- Core Infrastructure is a Product concept.
- Net New, Enhance, and Maintenance are Bucket/work-type concepts.
- Do not infer Bucket from Product name.

## Verification Completed Across Milestones

Recent verification included:

- Focused auth tests.
- Focused access-control tests.
- Focused reporting tests.
- Focused Jira import/sync and estimation policy tests.
- Full backend suites:
  - 91 passed during Entra SSO milestone.
  - 96 passed after forecast access hardening.
  - 99 passed after Jira bucket classification hardening.
  - 100 passed after Employment Type report dimension.
  - 101 passed after Program Area Reports/dashboard-hours redaction.
- Frontend production builds passed after interface changes.
- `git diff --check` passed before commits.

Latest known verification:

- `docker compose run --rm backend pytest` -> 101 passed.
- `docker run --rm -v "$PWD":/app -w /app/frontend node:22-alpine sh -lc "npm run build"` -> passed.
- `git diff --check` -> passed.

## Current State At Handoff

- Branch `develop` is synced with `origin/develop`.
- Latest commit is `ba02526 Restrict program area reports and dashboard hours`.
- Root package version is `0.1.50`.
- Frontend package/app version is `0.1.87`.
- Pushing `develop` triggers stage deployment.
- Retros are committed and should remain committed.
- Stage validation should focus on real role-specific users:
  - `sparc` break-glass Admin.
  - Admin-created user with temporary password.
  - Program Area View Only user assigned to Academics.
  - Leadership View Only user if needed.

## Known Open Items

- Entra App Registration values are still needed before SSO can be validated end to end.
- Product Detail pages need review if Program Area users continue to have access, because Product Detail may still expose hour-oriented context.
- A final-active-admin guardrail is documented as desirable, but confirm whether it has been fully enforced before relying on it.
- Program Area users with no assigned Program Area should receive a clear empty/no-area state; validate this on stage.
- If leadership wants the displayed Employment Type value `FTE` instead of `Employee`, handle that as an explicit normalization decision.
- Unknown Jira work type could use a future review queue or admin workflow.
- Entra logout currently clears the SPARC app session; full Microsoft federated logout can be added later if security/product wants it.

## Bryan / Codex Collaboration Notes

Bryan depends on retros as operational memory. Future agents should read retros first, especially before changing access control, Program Area logic, Jira/Rovo sync behavior, or reporting.

How Bryan tends to operate:

- He wants context before decisions, especially when terminology is fuzzy.
- He may be anxious when the model or product concept is unclear; reduce that anxiety by grounding answers in the actual code/docs.
- He values direct, practical answers, not vague architecture talk.
- Once a plan is agreed, keep moving and do not interrupt the flow unless there is a real blocker or risk.
- He expects specific milestones, concrete testability, and stage-validation guidance.
- He expects docs/retros to be committed because future Codex sessions rely on them.
- He expects commit and push once code is testable because pushes to GitHub trigger stage deployment.
- He prefers using Docker for local verification, then validating behavior on stage.
- He needs version/interface bumps for frontend changes and is sensitive to deployment breakage caused by overly long version strings.
- He wants the `sparc` Admin login preserved for backdoor/break-glass access.

## Guardrails For Future Agents

- Read `AGENTS.md`, `docs/product-brief.md`, `docs/access-control-plan.md`, and recent retros before changing core logic.
- Do not treat SPARC as a project management tool.
- Do not add task boards, sprint planning, due dates, Gantt charts, Bootstrap, Kubernetes, or direct Jira/Rovo access unless explicitly requested.
- Do not use `RoadmapItem.program_area` as an authorization boundary.
- Do not silently map unknown Jira work type to any Bucket.
- Do not expose bill rates, named Team Member details, reports, or dashboard hour quantities to roles that are not allowed to receive them.
- Do not rely on frontend hiding for security.
- Do not add Entra app roles for SPARC authorization unless the access strategy is explicitly changed.
- Do not auto-create SPARC users from Entra claims.
- Keep frontend/interface version strings short and bump them for frontend/interface changes.

## Recommended Next Steps

1. Validate latest stage deployment with `sparc` Admin and a Program Area View Only Academics user.
2. Confirm Reports is hidden and blocked for Program Area View Only.
3. Confirm Product Summary has no Forecast Hrs or Actual Hrs columns for Program Area View Only.
4. Confirm dashboard still scopes Products to assigned Program Area.
5. Review Product Detail access for Program Area View Only and decide whether to hide Product Detail entirely, redact hours there too, or allow a cost-only detail view.
6. Configure Entra stage secrets once DevOps provides Tenant ID, Client/Application ID, and client secret/certificate reference.
7. Validate SSO flow by creating a SPARC user by email, assigning role/Program Area, and then signing in through TDOE SSO.
