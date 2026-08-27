# SPARC-1 Program Area Work-Type Breakdown Retrospective

## Retrospective Metadata

- Date: 2026-08-27
- Project: SPARC
- Ticket: SPARC-1
- Milestone / Session: Program Area Product Detail work-type visibility
- Participants: Bryan Haddock and Codex
- Branch: `develop`
- Interface version: `0.1.105` to `0.1.106`
- Root release version: `0.1.68` to `0.1.69`

## Session Summary

SPARC-1 requests that Program Area stakeholders see the existing Product Detail work-type circle graphic for Maintenance, Enhance, and Net New. Leadership already received the widget, but Program Area View did not request it because the feature was tied to broad labor-hours access.

The implementation creates a narrow work-type-breakdown capability. Program Area View can request and render the aggregate FYTD chart only for Products that pass its existing Program Area authorization. It does not gain general labor-hours, Team Member, roster, Forecast matrix, or labor-detail access.

## Technical Outcomes

- Added `can_view_work_type_breakdown` to role capabilities for Admin, Leadership View Only, and Program Area View Only.
- Guarded the Product bucket-distribution endpoint with the narrow capability while retaining existing Product Program Area scope enforcement.
- Loaded and rendered the existing Product Detail pie chart for the new capability.
- Kept Program Area View free of hour tooltips and labeled its card `FYTD Work Type Breakdown`; Admin and Leadership retain the existing `FYTD Actualized Hours` title and hour tooltip.
- Added backend regression coverage for the Program Area capability and the endpoint guard.
- Updated the product brief and bumped the client interface version.

## Verification

- `git diff --check` passed.
- Focused backend access-control tests: `40 passed` (`backend/tests/test_auth.py` and `backend/tests/test_access_control_enforcement.py`).
- Clean Dockerfile frontend build passed with Node 22, TypeScript, and Vite for interface `0.1.106`.
- A direct mounted-workspace npm install is not a valid frontend verification path because npm inherits an unrelated root workspace `knip`/ESLint peer-dependency conflict; the Dockerfile's isolated frontend build stage matches the deployment install layout and passed.

## Handoff Notes

- Current state: SPARC-1 is implemented locally on `develop` and ready for verification, commit, and push.
- UAT acceptance: sign in as a Program Area View user with access to a Product's Program Area, open Product Detail, and verify the FYTD Work Type Breakdown circle shows Maintenance, Enhance, and Net New without hour tooltips. Confirm the user cannot access labor-hour or detailed labor screens.
