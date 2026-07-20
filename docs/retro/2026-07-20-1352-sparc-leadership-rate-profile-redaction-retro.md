# SPARC Leadership Rate And Profile Redaction Retrospective

## Session

- Date: 2026-07-20
- Milestone: Leadership rate-field omission and Team Member profile boundary
- Participants: Bryan Haddock, Florie, and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, and future SPARC Codex agents

## Stakeholder Feedback

Florie reported two related Leadership View Only problems. Restricted bill-rate values appeared throughout the interface as the word `Hidden`, which called attention to sensitive fields that should not be part of the Leadership experience. Team Member names also remained clickable and opened person-level profile pages even though Leadership should not have profile access.

## Decision

SPARC now distinguishes permission to see named labor rows from permission to open a Team Member profile. Leadership may continue to see Team Member names where those names are needed for all-area labor planning and analytics, but names render as plain text and person-level routes and APIs are denied. Admin retains linked names and full profiles.

Rate protection is expressed through omission. When the user cannot view rates, the interface does not render Bill Rate, Rate, Annual Cap cost, or other unavailable rate-derived values as visible placeholders. Backend response redaction remains the security boundary; UI omission is the corresponding presentation rule.

## Implementation

- Added the `can_view_team_member_profiles` capability: enabled for Admin and disabled for Leadership and Program Area roles.
- Added backend `require_team_member_profile_access` enforcement to Team Member detail, Product allocation, Actual worklog, and Roadmap Actual endpoints.
- Kept the Team Member roster endpoint available to Leadership under named-people access, with existing bill-rate redaction intact.
- Changed the Team Member detail route gate to require profile access.
- Made the shared Team Member name component capability-aware so Admin receives links and Leadership receives plain text.
- Applied the shared behavior to Product Team, Product Forecast bucket rows, Team roster and rankings, Team planning, Reported Values, and Roadmap Actuals.
- Omitted Bill Rate from Product Team and Team roster tables for restricted roles.
- Omitted Rate and Annual Cap columns from Team Member rankings for restricted roles and suppressed unavailable rate-derived cost sublines.
- Removed remaining bill-rate and derived-cost `Hidden` fallback text.
- Bumped root release version to `0.1.64` and frontend/interface version to `0.1.101`; both remain safely short for the deployment pipeline.

## Guardrails Preserved

- Leadership still sees all Program Areas, hours, aggregate costs, Team analytics, and Enterprise Reports.
- Program Area scope still comes exclusively from `Product.office` and user assignments.
- Team Members remain curated labor resources and are not conflated with SPARC application users or user roles.
- Bill rates remain redacted by backend serializers and exports; the frontend change does not replace backend enforcement.
- Product, Forecast, Actual, Roadmap, and Jira attribution logic are unchanged.

## Verification

- Full backend regression suite: 126 tests passed.
- Added route-dependency tests covering all four Team Member profile APIs.
- Added a role-capability regression proving Leadership can see names without profile or rate access while Admin retains profile access.
- Frontend TypeScript build: passed.
- Frontend Vite production build: passed.
- Source audit found no remaining rate-related `Hidden` placeholder.
- `git diff --check`: passed before documentation finalization.

## Stage Acceptance Checklist

1. Sign in as a Leadership View Only test user and open Team Management.
2. Confirm Team Member names are plain text and the Bill Rate roster column is absent.
3. Confirm Team Member Rankings has no Rate or Annual Cap columns and contains no `Hidden` values.
4. Open a Product and expand Product Team; confirm names are plain text and Bill Rate is absent.
5. Review Product bucket rows and Team planning; confirm names are not clickable and no rate text appears beneath them.
6. Enter a known `/team-members/{slug}` URL directly and confirm SPARC denies profile access.
7. Sign in as Admin and repeat the views; confirm Team Member links, profiles, and rate fields remain available.
8. Confirm Leadership still sees all Program Areas, allowed hours/costs, Team analytics, and Reports.

## Working Agreement

Bryan expects Codex to preserve momentum, investigate the existing structure before changing it, and complete a milestone through implementation, verification, documentation, commit, push, and stage readiness without repeatedly reopening settled product decisions. Retrospectives are required handoff infrastructure. Interface versions must be bumped for every frontend change, version identifiers must remain short enough for deployment constraints, and testable work should be pushed to `develop` so stage can be used for stakeholder validation.
