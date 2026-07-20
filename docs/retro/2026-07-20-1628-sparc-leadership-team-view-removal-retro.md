# SPARC Leadership Team View Removal Retrospective

## Session

- Date: 2026-07-20
- Milestone: Remove Team views from Leadership access
- Participants: Bryan Haddock, Florie, Vijay, and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, and future SPARC Codex agents

## Stakeholder Feedback

Florie confirmed that Leadership rate redaction passed stage testing: rates were no longer visible on the Dashboard or Reports page. She then clarified that the Team view should not be visible to Leadership at all. A separate question remains open with Bryan and Vijay about whether Product-by-Bucket Forecast and Product Team rostering should remain visible on Product pages.

## Decision

Team Management and Team Analytics are Admin-only. Leadership may still see Team Member and Team labels where they are valid dimensions of permitted Product and Report views, but those labels must not navigate into restricted Team or Team Member pages.

The Product Detail question is intentionally not resolved by this milestone. Product Team rostering and Product-by-Bucket Forecast remain visible under the existing Leadership behavior until Bryan, Florie, and Vijay make an explicit decision. No Product, Forecast, roster, Actual, Roadmap, or Jira data logic changed here.

## Implementation

- Added `can_view_team_pages`, enabled for Admin and disabled for Leadership and Program Area roles.
- Added backend `require_team_page_access` enforcement to the Team roadmap forecast-plan API.
- Changed `/team` and `/teams/:teamSlug` frontend route gates to use the Team-page capability.
- Removed the Team navigation button for users without Team-page access.
- Kept Team and Person dimensions available in Leadership Reports, but removed their restricted route links from backend report responses.
- Preserved Product report links for Leadership.
- Updated the Reports description so it only promises Person links to roles with Team Member profile access.
- Bumped root release version to `0.1.65` and frontend/interface version to `0.1.102`.

## Guardrails Preserved

- Backend authorization remains the security boundary; hiding the Team navigation button is not the only control.
- Leadership retains all-Program-Area Dashboard and Report visibility, permitted hours and costs, and named values in permitted views.
- Program Area scope remains based on `Product.office`.
- SPARC users, Team Members, Team labels, and labor roles remain separate concepts.
- Product Team and Product-by-Bucket Forecast behavior remains unchanged pending stakeholder direction.

## Verification

- Backend route-dependency coverage verifies the Team forecast-plan API requires Team-page access.
- Report regression coverage verifies Leadership Team and Person values are plain text while Product values remain linked.
- Role-capability coverage verifies Leadership lacks Team-page access and Admin retains it.
- Full backend regression suite: 128 tests passed.
- Frontend TypeScript and Vite production build: passed.
- `git diff --check`: passed before commit.

## Stage Acceptance Checklist

1. Sign in as Leadership View Only and confirm there is no Team navigation button.
2. Enter `/team` directly and confirm Team Management is denied.
3. Enter a known `/teams/{team-slug}` URL directly and confirm Team Analytics is denied.
4. Open Reports and use Team and Person dimensions; confirm values display as plain text rather than links.
5. Confirm Product values in Reports still link to Product Detail.
6. Confirm Dashboard, Reports, permitted hours/costs, and all-Program-Area visibility still work.
7. Sign in as Admin and confirm Team navigation, Team Management, Team Analytics, and Team planning remain available.
8. Confirm Product Team and Product-by-Bucket Forecast behavior has not changed for Leadership while the stakeholder decision remains pending.

## Working Agreement

Bryan expects approved feedback to move through implementation, regression coverage, documentation, commit, push, and stage verification without reopening settled decisions. Pending product questions must be recorded and left unchanged until an explicit decision is made. Retrospectives are required handoff infrastructure, every interface change requires a short version bump, and testable work is pushed to `develop` for stage acceptance.
