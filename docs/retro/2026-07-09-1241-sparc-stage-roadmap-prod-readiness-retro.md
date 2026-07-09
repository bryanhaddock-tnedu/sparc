# SPARC Retrospective - 2026-07-09 12:41

## Retrospective Metadata

- Date: 2026-07-09
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Stage hardening, roadmap-informed planning, enterprise reporting, and production access-control planning
- Participants: Bryan Haddock and Codex acting as SPARC engineering partner
- Related files / branches / tickets:
  - Branch: `develop`
  - `docs/product-brief.md`
  - `docs/deployment.md`
  - `docs/roadmap-billing-milestones.md`
  - `backend/app/models/entities.py`
  - `backend/app/services/aggregations.py`
  - `backend/app/services/forecasting.py`
  - `backend/app/services/jira_rovo.py`
  - `backend/app/services/roadmap.py`
  - `backend/app/services/roadmap_forecasting.py`
  - `backend/app/services/reporting.py`
  - `backend/app/services/auth.py`
  - `backend/app/api/auth.py`
  - `backend/app/api/teams.py`
  - `backend/app/api/reports.py`
  - `frontend/src/pages/DashboardPage.tsx`
  - `frontend/src/pages/ProductDetailPage.tsx`
  - `frontend/src/pages/ProductSettingsPage.tsx`
  - `frontend/src/pages/TeamManagementPage.tsx`
  - `frontend/src/pages/TeamAnalyticsPage.tsx`
  - `frontend/src/pages/TeamMemberDetailPage.tsx`
  - `frontend/src/pages/ReportsPage.tsx`
  - `frontend/src/components/TeamMemberRankingsTable.tsx`
  - `frontend/public/app-version.json`
- Handoff target bot or teammate: New SPARC Codex thread, Bryan, Florie, DevOps, and future production-readiness reviewers

## Session Summary

- What did we work on?
  - We moved SPARC from stage deployment scaffolding into a much broader stage-ready application surface.
  - Work covered dashboard month scoping, Team overview improvements, Team Member detail analytics, Product org metadata, Product detail cleanup, roadmap actual attribution, roadmap-informed team planning, enterprise cost reports, daily Jira sync, URL slug hygiene, frontend cache busting, and production authentication/authorization planning.
  - We also spent significant time reconciling the role of Jira roadmap data: roadmap data is useful planning context, but Forecast remains SPARC-owned Product / Team Member / Bucket / Fiscal Month data.
- Why did this work matter?
  - SPARC is now being used under real budget and planning pressure. The app needs to be trustworthy enough for managers to enter Forecast hours without losing work, and clear enough for leadership and program areas to review costs without seeing inappropriate detail.
  - The project is moving toward a production audience, so access control, role-based visibility, and data scoping are no longer optional polish.
- What was completed?
  - Added basic app authentication for stage.
  - Added frontend app-version cache-busting and made interface version bumps a required rule.
  - Added Dashboard Fiscal Month / Entire FY scoping, then defaulted the Dashboard to Entire FY.
  - Added compact dashboard period selector behavior and future-month Actual bar hiding.
  - Added dashboard Labor Mix resource counts by employment type and role.
  - Added Team Member creation on the Team overview page and moved it below Team visualizations.
  - Grouped Team overview roster by Team and improved Team rankings.
  - Added Team Member detail actual worklog audit.
  - Added Product Office and Division fields, with Office effectively becoming the SPARC Program Area access scope.
  - Added Product role cost summary and streamlined Product detail dashboard metrics.
  - Added Product, Team, and Team Member slug URLs.
  - Added roadmap billing attribution, roadmap actual gaps, roadmap item mapping, product-scoped roadmap deliverables, roadmap schedule parsing, and schedule month highlighting.
  - Added Team Analytics pages and a Product/Bucket team planning surface.
  - Corrected the team planning model so it saves canonical Forecast cells instead of maintaining separate roadmap forecast data.
  - Added team planner autosave, autosave hardening, and navigation flush behavior.
  - Added Enterprise Reports with XLSX export and sortable dimensions.
  - Added daily Jira Actual sync before the business day.
  - Began production access-control design: Entra for authentication, SPARC-local roles and Program Area mappings for authorization.
- What remains in flight?
  - Entra SSO implementation.
  - Local SPARC user, role, permission, and Program Area access-scope management.
  - Backend-enforced redaction of bill rates and scoped data.
  - Admin UI for assigning user roles and Program Area visibility.
  - Program Area scoped dashboard/report views.
  - Final terminology cleanup: Office and Program Area need to be treated as the same user-facing concept, with Program Area preferred.
  - Forecast autosave still needs extra trust-building and test coverage because lost or disappearing Forecast edits caused major friction.

## Technical Outcomes

- What code or docs changed?
  - Backend auth added a basic username/password session for stage.
  - Backend aggregation and reporting services grew significantly to support dashboard scoping, Labor Mix counts, Team rankings, Product/Team Member views, and Enterprise Reports.
  - Forecast writes were expanded across Product detail, Team Member detail, and Team Analytics planning surfaces.
  - Roadmap services added read-only Jira roadmap item ingestion, fiscal year labels, category-to-bucket mapping, program-area metadata, deliverable relationships, actual-hour attribution, schedule month parsing, and mapping workbench support.
  - Frontend pages were repeatedly refined for dashboard, product, team, team member, admin, reports, and integrations workflows.
  - Product brief and deployment docs were updated to capture newer rules, including slug URLs, interface version bumping, and scheduled Jira sync.
- What behaviors were added, removed, or fixed?
  - Added clickable Product and Team Member names in more places.
  - Added product/team/member slug routes and stopped generating uppercase or encoded-space URLs.
  - Moved unmapped Jira projects to the bottom of Product Settings.
  - Fixed stale deleted Jira worklogs remaining after sync by deleting stale worklog IDs.
  - Limited live Jira Actual sync to the current fiscal year.
  - Fixed migration-name length issue that blocked stage deployment.
  - Added visible roadmap schedule month shading, eventually switching from subtle text color to background shading.
  - Removed number-input spinner controls from planning cells.
  - Reduced roadmap noise on Product pages after it became clear the planning work belongs on Team pages and Forecast tables.
  - Changed Team planning so entries save to the same canonical Forecast data used by Product and Team Member pages.
- What architecture or design decisions were made?
  - Forecast is canonical at Product + Team Member + Bucket + Fiscal Month + Fiscal Year.
  - Roadmap Items are read-only Jira context. They may inform which Products/Buckets/months matter, but they must not become the Forecast grain.
  - Roadmap sync and Worklog sync are separate pipelines. Worklog sync owns Actual hours. Roadmap sync owns Roadmap Items and ticket relationships.
  - Product/Bucket planning on a Team page must read and write the same Forecast entries shown on Product Detail and Team Member Detail.
  - Product names, Team names, and Team Member names should link to slug-based routes wherever they appear.
  - App-owned Jira/Rovo server-side sync remains the integration model.
  - Office and Program Area should be treated as the same product-level concept. The database currently stores it as `Product.office`; user-facing UI should move toward Program Area.
  - Entra should authenticate users only. SPARC should own local authorization, roles, capabilities, and Program Area assignments.
- What technical constraints or unknowns came up?
  - Stage deployments can lag after GitHub Actions pushes because the image push does not immediately mean the new pod is live.
  - UAT/stage can report a new `/api/app-version` only after the new instance is actually added behind the load balancer.
  - Cluster capacity and failed DB migrations can make "it deployed" and "the app is running new code" diverge.
  - Long-running conversations increased the risk of losing the current product decision, especially around roadmap versus Forecast.
  - Roadmap schedule fields from Jira Product Discovery need careful parsing because visible month ranges are human-friendly strings, not necessarily clean dates.

## Verification

- What did we test or validate?
  - Backend tests were run throughout the session, reaching a larger passing suite after later changes.
  - Frontend production builds were run after interface changes.
  - Stage app version was checked through `/api/app-version`.
  - User and product director validated changes directly in UAT/stage using screenshots and real planning data.
  - Actual deleted Jira worklog behavior was tested and fixed through sync logic.
  - Roadmap schedule highlighting was verified visually after multiple iterations.
  - Enterprise report XLSX export behavior was added and exercised.
- What was not tested?
  - Entra SSO, because App Registration is still pending.
  - Role-based authorization, because it has not been built yet.
  - Program Area security filtering across every API.
  - Read-only cost/rate redaction across Product, Team, Team Member, Dashboard, Reports, and export endpoints.
  - Full browser regression across every planning surface after each autosave iteration.
- What still feels risky?
  - Forecast autosave trust. The user lost or appeared to lose entered Forecast values, which is a major confidence issue.
  - Forecast parity across Team page, Product page, and Team Member page must remain airtight.
  - Roadmap schedule data can still be misunderstood if SPARC presents it as more authoritative than it is.
  - Program Area scoped access is a security boundary and must be backend-enforced.
  - Cost visibility for Program Area users can imply bill rates if person-level detail and hours are exposed together.
- What evidence do we have that the current state works?
  - Commit history shows repeated fixes landing and being pushed to stage.
  - Tests/builds passed at multiple points.
  - Stage version checks confirmed new hashes after deployment lag was understood.
  - User validation confirmed several later UI changes were visible and useful, especially roadmap-informed product/bucket planning after simplification.

## Collaboration Review

- What parts of the collaboration worked especially well?
  - The user supplied many screenshots, which made it possible to react to the actual product experience instead of imagined UI states.
  - The product director's feedback was brought in quickly, giving the work a real stakeholder signal.
  - The user pushed hard on conceptual clarity, especially when roadmap planning started to drift away from SPARC's Forecast source of truth.
  - Direct stage validation exposed deployment, cache, migration, and autosave problems earlier than a slower review cycle would have.
- What kind of prompts or instructions helped most?
  - "This should be the same Forecast data everywhere" was the most important product rule.
  - "Roadmap is only an association/context" reset the planning model correctly.
  - Screenshots with specific target rows or fields helped more than general UI descriptions.
  - Asking for practical testing instructions helped convert implementation into useful validation steps.
- What communication style was most effective?
  - Short, direct updates while working.
  - Immediate acknowledgement when a direction was wrong.
  - Plain explanations of what was wrong, what would be changed, and where to verify it.
  - Practical product-owner language over abstract architecture when the user was under deadline pressure.
- Where did we lose momentum or create confusion?
  - Roadmap forecasting was initially over-modeled. The app drifted toward Roadmap Item / Deliverable planning when the user needed Product/Bucket Forecast planning with roadmap-informed month context.
  - Schedule highlighting was too subtle for too long.
  - Stage deployment visibility caused confusion until the five-minute deploy delay, cluster capacity issue, and app-version endpoint behavior were clarified.
  - Autosave behavior damaged trust because Forecast entries appeared to disappear after the user spent time entering data.
  - Office versus Program Area terminology became confusing and needs standardization.
- What should future bots know about how the user likes to work?
  - Bryan is direct, fast-moving, and often working under real operational pressure.
  - He wants the app to reduce his workload, not create extra conceptual or navigation burden.
  - He responds well to clear ownership: say what is happening, fix it, verify it, and do not over-explain while he is trying to finish work.
  - He will challenge unclear product logic quickly. Treat that as useful signal, not noise.
  - He values stage visibility and deploy confidence because product stakeholders are actively testing.

## Workflow Preferences Learned

- Preferred interaction style:
  - Proactive, implementation-oriented, and direct.
  - Do not ask for clarification when the product intent is clear enough to act.
  - Do ask when a decision affects security, access, or data visibility.
- Preferred pacing:
  - Move quickly, but keep short progress updates during longer work.
  - For high-risk data/security work, pause long enough to state the model before coding.
- Preferred level of detail:
  - Concise operational details in conversation.
  - More complete detail in docs, retros, tickets, and handoff artifacts.
- Things that increase focus:
  - Screenshots.
  - Specific page URLs.
  - Exact Product, Team Member, Bucket, Fiscal Month examples.
  - Clear "where do I verify this in stage" instructions.
  - Explicit app version/hash confirmation when deployment is involved.
- Things that create friction:
  - Losing entered Forecast values.
  - UI that requires horizontal scrolling for July-through-June planning grids.
  - Subtle visual cues that are hard to distinguish.
  - Roadmap labels and deliverable details taking over the planning workflow.
  - Deployment status explanations that do not map to what the user can see.
  - Any generated URL with spaces, capitalization, or numeric IDs where slugs should be used.
- Good defaults for future sessions:
  - Preserve Forecast as the core product-owned planning data.
  - Treat roadmap data as read-only context unless explicitly asked otherwise.
  - Use obvious background shading for schedule/month context.
  - Keep July-through-June grids visible without horizontal scrolling.
  - Bump the frontend/interface version for every interface change.
  - Push only after tests/builds pass or clearly state what could not be run.

## Friction And Weaknesses

- What slowed us down?
  - Repeated stage deploy uncertainty.
  - Insufficient early clarity around roadmap data's role.
  - Autosave and canonical Forecast synchronization problems.
  - The long thread made it harder to keep the current user intent separate from older implementation assumptions.
- What did the system make the user manage unnecessarily?
  - The user had to repeatedly check whether stage had updated.
  - The user had to manually detect missing Forecast values across Team, Product, and Team Member pages.
  - The user had to explain that roadmap data should not become the planning data model.
  - The user had to fight UI layout issues while trying to finish budget planning.
- What did the bot misunderstand?
  - It initially treated roadmap items and deliverables as a planning structure instead of background context.
  - It did not immediately preserve the simple rule that Forecast entered anywhere must appear everywhere.
  - It underestimated how harmful subtle schedule highlighting and horizontal scrolling were during real planning work.
  - It did not move quickly enough from "show roadmap detail" to "show product/bucket/month planning context."
- What technical weaknesses showed up?
  - No production role/permission model yet.
  - Basic auth is not sufficient for production.
  - No local SPARC user mapping table for Entra users.
  - No backend data-scope service for Program Area visibility.
  - Forecast autosave needs stronger reliability and observability.
  - UI cache invalidation required repeated reinforcement before it became a standing rule.
- What workflow weaknesses showed up?
  - The app is now used in real planning meetings, so "eventually consistent" or "refresh and see" UX is not enough.
  - The team needs tighter release notes or stage verification after pushes.
  - Security and visibility requirements need to be designed before UI hides data, because UI-only hiding is not protection.

## Action Items

- [ ] Product / UX improvement: Rename user-facing Product `Office` labels to Program Area where that concept is used for reporting or access.
- [ ] Product / UX improvement: Build a Program Area scoped dashboard for Program Area View users that emphasizes dollars and hides editing, rates, and likely person-level detail.
- [ ] Product / UX improvement: Keep the Team page planning surface Product/Bucket-focused and use roadmap data only as schedule/context.
- [ ] Engine / logic improvement: Add a canonical Forecast write/read parity test suite covering Team page, Product page, and Team Member page.
- [ ] Engine / logic improvement: Add durable autosave behavior and visible save status for Forecast cells, including retry/failure handling.
- [ ] Engine / logic improvement: Add SPARC user, role, and Program Area assignment models.
- [ ] Engine / logic improvement: Add backend permission and data-scope dependencies before adding more role-specific UI.
- [ ] Documentation improvement: Document the access model: Entra authenticates; SPARC authorizes; Product.office is the Program Area scope until renamed.
- [ ] Documentation improvement: Add an Entra App Registration ticket/checklist for stage and production.
- [ ] Documentation improvement: Document roadmap data rules: roadmap sync supplies context and Actual attribution only; Forecast remains SPARC-owned.
- [ ] Collaboration improvement: Start the next thread by reading this retro, the product brief, auth service, and the current Team Analytics forecast code before changing anything.
- [ ] Testing / validation improvement: Add authorization tests proving Program Area users cannot retrieve out-of-scope Products, Forecasts, Actuals, Reports, exports, or Team Member details.
- [ ] Testing / validation improvement: Add redaction tests proving restricted users cannot retrieve bill rates from any API or XLSX export.

## Open Questions

- What still needs clarification?
  - Should Program Area View users see only dollars, or can they see hours at aggregate level?
  - Should Program Area View users see named Team Members at all, or only Product/Bucket summaries?
  - Can a Program Area user be mapped to multiple Program Areas?
  - Should Leadership View Only see all person-level rows, or only aggregate hours and dollars?
  - Should cost values be visible when bill rates are hidden, knowing that person-level hours plus cost can imply rates?
  - Should the user-facing field be fully renamed from Office to Program Area now, or should the DB column stay `office` for a later migration?
- What decisions are deferred?
  - Exact Entra App Registration values are deferred to DevOps.
  - Whether Entra groups or app roles are used later is deferred, but current direction is Entra authentication only and SPARC-local authorization.
  - Final production role names and allowed pages/actions need one more explicit sign-off.
  - Full bill-rate versioning remains future state.
- What assumptions should be revisited later?
  - Product.office is the correct Program Area security boundary.
  - Program Area values are Academics, Operations, Programs, Deputy Commissioner, Commissioners Office, and General Counsel.
  - Forecast should remain editable by Admin and future Planner-type users only.
  - Roadmap schedule fields from Jira are reliable enough for month context after sync.

## Handoff Notes

- Current state:
  - SPARC has a broad stage feature set: Dashboard, Products, Product Detail, Team Management, Team Analytics, Team Member Detail, Integrations/Admin, Enterprise Reports, Jira Actual sync, roadmap actual attribution, roadmap schedule context, and forecast planning.
  - The app is still using basic auth for stage.
  - Production authentication/authorization has been discussed but not implemented.
  - The current direction is Entra SSO for authentication and SPARC-local roles/permissions/program-area mappings for authorization.
- Recommended next step:
  - Build the SPARC-local access model first: `User`, `UserRole`, Program Area assignments, capability mapping, and backend permission/data-scope dependencies.
  - Then add Entra SSO as the authentication source feeding that local user model.
  - After backend enforcement exists, update UI to hide/disable actions and redact restricted data.
- Things to avoid:
  - Do not use roadmap items as the Forecast grain.
  - Do not add project management behavior, task boards, sprint planning, timelines, due dates, or Gantt charts.
  - Do not implement access control only in React.
  - Do not expose bill rates through any API or export for restricted roles.
  - Do not generate URLs with spaces, uppercase names, or IDs when a slug is available.
  - Do not forget to bump the JavaScript/interface version after UI changes.
  - Do not make July-through-June monthly planning grids horizontally scroll by default.
- Important context for the next bot:
  - The user is trying to make SPARC useful for real budget planning and leadership/program-area review.
  - Forecast reliability is emotionally and operationally important because the user has already spent real time entering Forecast values.
  - Product/Bucket/Team Member/Fiscal Month Forecast data must be one shared truth across Team page, Product page, and Team Member page.
  - Roadmap data should inform "what Product/Bucket matters and which months are relevant" but should stay in the background unless explicitly needed for Actual attribution or billing evidence.
  - Office and Program Area are the same business concept for SPARC access planning; prefer Program Area in user-facing language.
- Commands or files the next bot should start with:
  - `sed -n '1,220p' docs/product-brief.md`
  - `sed -n '1,260p' docs/retro/2026-07-09-1241-sparc-stage-roadmap-prod-readiness-retro.md`
  - `sed -n '1,220p' backend/app/services/auth.py`
  - `sed -n '1,180p' backend/app/api/auth.py`
  - `sed -n '1,120p' backend/app/api/__init__.py`
  - `sed -n '1,140p' backend/app/models/entities.py`
  - `sed -n '1,260p' backend/app/services/aggregations.py`
  - `sed -n '1,260p' frontend/src/lib/auth.tsx`
  - `sed -n '1,220p' frontend/src/pages/TeamAnalyticsPage.tsx`
  - `pytest backend/tests`
  - `npm --prefix frontend run build`

## Next Thread Starter

Use this prompt to start the next SPARC thread:

```text
We are continuing SPARC production-readiness work. Please first read:

- docs/product-brief.md
- docs/retro/2026-07-09-1241-sparc-stage-roadmap-prod-readiness-retro.md
- backend/app/services/auth.py
- backend/app/api/auth.py
- backend/app/api/__init__.py
- backend/app/models/entities.py
- backend/app/services/aggregations.py
- frontend/src/lib/auth.tsx
- frontend/src/types/api.ts

Current objective:

We need to clarify and then implement the Program Area access model and get back to setting up Entra SSO.

Important concept:

Florie said Office and Program Area are the same business concept. In the current code, the Product model has `office` and `division`. For access-control planning, `Product.office` should be treated as the canonical SPARC Program Area scope. The UI should probably call this Program Area going forward, even if the database column stays `office` for now.

Current Program Area / Office values:

- Academics
- Operations
- Programs
- Deputy Commissioner
- Commissioners Office
- General Counsel

Division is lower-level org metadata under Program Area. Division is useful for reporting/filtering later, but it should not be the first production access-control boundary.

Roadmap note:

Roadmap items also carry `program_area` from Jira agency office metadata. That is useful context for roadmap actuals and billing review, but it should not become the security boundary. The security boundary should be the SPARC-owned Product Program Area, currently `Product.office`.

Authentication / authorization decision:

Use Entra only for authentication. Entra tells SPARC who the user is. SPARC owns authorization locally.

SPARC needs local user/access records with:

- Entra object ID
- email
- display name
- role
- assigned Program Area values when applicable
- active/inactive status

Initial roles:

1. Admin
   - Can view and edit everything.
   - Can see hours, dollars, and bill rates.
   - Can run admin/sync/import/config operations.

2. Leadership View Only
   - Can view all Program Areas.
   - Cannot edit.
   - Can see hours and dollars.
   - Should not see bill rates.

3. Program Area View
   - Can only see data for assigned Program Area(s).
   - Cannot edit.
   - Should not see bill rates.
   - Intended to show dollars for that Program Area. Need one more product decision on whether this role can see hours or person-level detail, because hours + cost can imply rates.
   - If a Program Area View user has no assigned Program Area, they should see no SPARC data and a clear "No Program Area assigned" message.

Backend enforcement is mandatory:

- Do not rely on hiding UI controls only.
- Every API endpoint that returns Products, Forecasts, Actuals, Team Members, Reports, Dashboard data, or XLSX exports must respect the user's role and Program Area scope.
- Restricted users must not be able to retrieve bill rates by directly calling an API.

Suggested implementation sequence:

1. Add local SPARC access model first:
   - User table
   - User role enum/field
   - Program Area assignment table or JSON/list field
   - Capability helpers
   - Test fixtures

2. Expand auth status:
   - Return authenticated user identity
   - Return role
   - Return capabilities such as can_edit_forecast, can_admin, can_view_rates, can_view_hours, can_view_costs
   - Keep basic auth fallback for local/stage while Entra App Registration is pending

3. Add backend permission and scoping dependencies:
   - require_admin
   - require_write_access
   - current_user
   - apply_program_area_scope(query/model)

4. Add redaction:
   - Hide bill_rate from restricted API responses
   - Ensure XLSX exports follow the same rule

5. Add Admin Access UI:
   - List signed-in/known SPARC users
   - Assign role
   - Assign Program Area(s)
   - Activate/deactivate user

6. Add Entra SSO:
   - App Registration for SPARC Stage
   - Single tenant
   - Web redirect URI: https://sparc.uat.tnedu.gov/api/auth/entra/callback
   - Logout redirect: https://sparc.uat.tnedu.gov/
   - Scopes: openid, profile, email
   - No Graph permissions needed initially
   - No Entra app roles needed initially because SPARC manages roles internally

7. Update frontend:
   - Use auth status capabilities to hide/disable actions
   - Update Office labels to Program Area where user-facing
   - Provide a Program Area scoped dashboard/report view for Program Area users

Questions to clarify before or during implementation:

- Should Program Area View users see aggregate hours, or dollars only?
- Should Program Area View users see named Team Members, or only Product/Bucket summaries?
- Can one Program Area user be assigned to multiple Program Areas?
- Should Leadership View Only see person-level detail, or only team/product/program summaries?
- Should we rename the database column from office to program_area now, or keep `office` internally and only rename the UI label?

Rules to preserve:

- SPARC is a labor forecasting and cost intelligence app, not a project management tool.
- Forecast is canonical Product + Team Member + Bucket + Fiscal Month + Fiscal Year data.
- Roadmap data is context and actual attribution evidence, not the Forecast grain.
- For every frontend/interface change, bump the JavaScript/interface version.
```
