# SPARC Leadership Product Labor Detail Removal Retrospective

## Session

- Date: 2026-07-22
- Milestone: Apply Vijay's final Leadership Product-detail visibility decision
- Participants: Bryan Haddock, Florie, Vijay, and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, and future SPARC Codex agents

## Stakeholder Feedback

Florie reported that Leadership rate omission passed stage testing and confirmed Team pages should be removed. She then asked whether Product-by-Bucket Forecast and Product Team rostering should also be hidden from Leadership for consistency. Vijay answered, "hide it," and Bryan confirmed that this decision should be implemented without reopening the settled scope.

## Decision

Detailed labor views are Admin-only. Leadership View Only retains all-Program-Area access to aggregate Product budget, hours, costs, actual-hours bucket distribution, Product navigation, and Enterprise Reports. Leadership may still see Team and Person names as plain-text Report dimensions, but cannot retrieve or view Product Team rostering, Product-by-Bucket Forecast matrices, role-cost details, Reported Values, Team Member profiles, Team pages, or their raw labor-detail APIs.

Program Area View Only keeps its existing Product scope and no-hours redaction while receiving the same high-level Product page shape. The decision changes authorization and presentation only. It does not delete or alter Product Team assignments, Forecasts, Actuals, Estimates, Roadmap data, Jira mappings, or sync behavior.

## Implementation

- Added `can_view_labor_details`, enabled only for Admin.
- Changed `require_labor_detail_access` to enforce that explicit capability rather than inferring access from hours plus named-person permissions.
- Applied the labor-detail guard to raw Forecast reads, Product Team reads, Product bucket-table reads, Product Roadmap Actual reads, Team Member roster reads, Estimation run/detail reads, story-point metrics, delivery-flow detail, and Reported Values.
- Kept Product summary and aggregate bucket-distribution APIs available according to existing Product scope and hours capabilities.
- Redacted Dashboard Team Member totals and per-Product Team Member counts from restricted API responses.
- Removed the Dashboard Team Members column and sort option when labor-detail access is absent.
- Removed Product Team, role-cost breakdown, Forecast Line controls, Product-by-Bucket matrices, and Reported Values from restricted Product Detail views without showing a placeholder that calls attention to hidden data.
- Preserved Admin behavior and all edit workflows.
- Updated the product brief, access-control plan, and living milestone tracker.
- Bumped the short root release version to `0.1.66` and frontend/interface version to `0.1.103`.

## Guardrails Preserved

- Backend authorization is the security boundary; the implementation does not rely on hidden navigation or conditional rendering alone.
- `can_view_named_people` remains separate because Leadership still needs Team and Person values in authorized Reports.
- Program Area scope remains based on `Product.office`, never `RoadmapItem.program_area`.
- Forecast, Actual, Estimated, Reported, and Roadmap values remain separate.
- Team Members remain labor resources, not SPARC users or access roles.
- No database migration or data rewrite was required.

## Verification

- Focused authentication and access-control tests: 39 passed.
- Full backend regression suite: 138 passed.
- Frontend TypeScript build: passed.
- Frontend Vite production build: passed. The existing large-chunk advisory remains non-blocking.
- `git diff --check`: passed.
- GitHub Actions Docker image build and registry push for the implementation commit: passed.
- Stage `/api/app-version` reported the exact implementation commit, and `/app-version.json` reported interface version `0.1.103`.
- The live content-hashed JavaScript bundle contains `can_view_labor_details` and no longer contains the removed restricted-role placeholder text.

## Stage Acceptance Checklist

1. Sign in as Leadership View Only and confirm Dashboard Product Summary has no Team Members column or Team Members sort option.
2. Open a Product and confirm the header, Budget Tracker, Product snapshot, aggregate hours/costs, and actual-hours bucket chart remain visible.
3. Confirm Product role-cost detail, Product Team, Forecast Lines, Product-by-Bucket Forecast matrices, and Reported Values are absent with no `Hidden` placeholder.
4. Confirm Reports remain visible and Team/Person dimensions still show plain-text values without profile or Team links.
5. Confirm Team navigation, Team pages, and Team Member profile pages remain unavailable.
6. Sign in as Admin and confirm Dashboard Team Member counts, Product Team, role-cost detail, Forecast Lines, Product bucket matrices, Reported Values, Team pages, and edit workflows remain available.
7. Confirm existing Forecast, Actual, Product Team, Roadmap, and Jira data is unchanged.

## Working Agreement

Bryan expects explicit stakeholder decisions to move through implementation, regression coverage, durable documentation, commit, push, and exact stage-release verification without repeatedly reopening settled scope. Retrospectives are required handoff infrastructure. Every frontend/interface change receives a short version bump because longer version strings have previously broken deployment. Testable work is committed and pushed to `develop`, which triggers the stage deployment workflow.

## Deployment

- Implementation commit: `1df7a0892afe47491fed0300958069a68585a4dd`
- GitHub Actions run: `29950405295`, completed successfully
- Stage verification: exact implementation SHA and interface version `0.1.103` confirmed at 2026-07-22 14:31 CDT
