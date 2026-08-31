# SPARC-5 Leadership Role Summary Retrospective

## Retrospective Metadata

- Date: 2026-08-31
- Project: SPARC
- Ticket: SPARC-5
- Milestone / Session: Leadership Product role aggregation
- Participants: Bryan Haddock, Florie, and Codex
- Branch: `develop`
- Interface version: `0.1.106` to `0.1.107`
- Root release version: `0.1.69` to `0.1.70`

## Session Summary

Leadership requested a Product Detail view that combines labor by role instead of making Team Member names the primary planning surface. Florie confirmed that `Dev` and `Sr. Dev` must remain separate because bill rates and cost variance matter; Product Owner is also a Team Member job role for this organization. Forecasting remains individual-contributor based.

## Technical Outcomes

- Added a read-only Product role summary that aggregates selected-fiscal-year canonical Forecast and Actual values by exact Team Member job-role title.
- Displays Forecast Hours, Forecast Cost, Actual Hours, Actual Cost, and Actual minus Forecast Cost by role.
- Uses each contributor's existing bill rate when calculating costs, so a role total remains financially accurate without exposing person names or bill rates.
- Grants the view to Admin and Leadership View Only through a narrow `can_view_role_breakdown` capability; Program Area View Only remains excluded.
- Preserves Product Program Area authorization at the API boundary.
- Removed the superseded Admin-only role-cost card in favor of the richer role summary.
- No role-level Forecast entry, allocation, or automated distribution logic was introduced.

## Verification

- Focused backend tests: `110 passed` across authentication, access-control enforcement, and service coverage. They verify exact role separation, contributor-rate cost aggregation, endpoint authorization, and Program Area exclusion.
- Clean Dockerfile frontend build passed with Node 22, TypeScript, and Vite for interface `0.1.107`.

## Handoff Notes

- UAT acceptance: Leadership should see a Product Detail Role Forecast and Actuals table with separate Dev and Sr. Dev rows, no contributor names or bill rates, and correct aggregate Forecast/Actual cost variance. Program Area View must not see the section. Admin Forecast entry must remain person based.
