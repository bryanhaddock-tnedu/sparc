# SPARC Retrospective - 2026-07-15 15:08

## Retrospective Metadata

- Date: 2026-07-15
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Role-aware post-login landing
- Participants: Bryan Haddock and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, and future SPARC Codex sessions

## Report And Root Cause

Florie signed out of the Admin Users page and then signed in with a non-admin test user. SPARC displayed `Admin tools are not available for your role`.

The authorization result was correct, but the navigation flow was not. Signing out displayed the login screen without changing the browser's `/admin?tab=users` URL. A successful local login updated authentication state but preserved that restricted URL, so the newly signed-in Leadership or Program Area user immediately encountered the Admin capability gate.

## Completed Work

- Successful local sign-in now replaces the current browser location with the Dashboard route (`/`).
- The Admin navigation item remains hidden for non-admin roles.
- Direct access to `/admin` remains blocked by the frontend capability gate.
- Admin APIs remain protected by backend `require_admin` enforcement.
- Entra sign-in already redirects to the configured frontend origin, so its landing behavior remains consistent with this rule.
- Updated the product brief to require a safe Dashboard landing after sign-in while preserving direct-route authorization.
- Bumped root release version to `0.1.57` and frontend/interface version to `0.1.94`.

## Verification

- Frontend TypeScript compilation and production build passed with `npm run build` in Docker.
- `git diff --check` passed.
- No backend behavior or database schema changed; no migration was required.
- The known repository ESLint 9 configuration gap remains unrelated to this change.

## Stage Validation

1. Sign in as `sparc` and open Admin > Users.
2. Sign out while still on that page.
3. Sign in with a Leadership View Only or Program Area View Only test user.
4. Confirm SPARC opens the Dashboard rather than an Admin authorization error.
5. Confirm the Admin navigation button is absent.
6. Confirm manually entering `/admin` is still denied.

## Working Agreement

Bryan expects testable milestones to be documented in retrospectives, committed, pushed to `develop`, and verified on stage. Codex should maintain development flow, investigate reports across both interface and backend enforcement, use short version strings, bump the interface version for every frontend change, and avoid weakening security merely to hide an awkward user experience.
