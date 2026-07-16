# SPARC Retrospective - 2026-07-16 09:30

## Retrospective Metadata

- Date: 2026-07-16
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Long-lived browser session refresh hardening
- Participants: Bryan Haddock and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, and future SPARC Codex sessions

## Report And Investigation

Florie reported that the Leadership test-user fixes still did not work in stage. Her screenshot showed a Leadership View Only row with explicit Program Area checkboxes. The released Admin UI should instead display `All Program Areas` for Leadership users.

Direct stage inspection established that deployment itself was correct:

- `/api/app-version` reported commit `4b6500f1a1a1a5b741f72a681d2db5c4de649e7d`.
- The live, content-hashed JavaScript bundle contained `All Program Areas`.
- The live bundle also contained the non-admin Dashboard login redirect.
- Stage HTML used no-cache response headers and pointed to the new bundle.

The screenshot therefore came from an already-open browser tab still executing the prior JavaScript bundle.

## Root Cause

SPARC's browser version guard checked `/api/app-version` only once when the JavaScript application initially started. If a browser tab was already open before a deployment, that one check saw the then-current version and never ran again. Leaving or returning to that tab after deployment did not trigger a version comparison, so the stale interface could remain indefinitely.

## Completed Work

- Retained the immediate startup version check.
- Added a version check every 60 seconds.
- Added a version check whenever the browser window receives focus.
- Added a version check whenever the tab becomes visible.
- Added an in-flight guard so simultaneous timer/focus/visibility events cannot issue duplicate checks.
- Preserved cache-busted replacement navigation and the existing bounded reload-attempt protection.
- Updated deployment documentation with the complete browser-refresh behavior.
- Bumped root release version to `0.1.58` and frontend/interface version to `0.1.95`.

## Verification

- Live stage HTML, asset headers, build SHA, and deployed bundle markers were inspected directly.
- Frontend TypeScript compilation and production build passed with `npm run build` in Docker.
- `git diff --check` passed.
- No backend behavior or database schema changed; no migration was required.

## Immediate And Future Validation

- For the tab that was already stale, one `Cmd+Shift+R` immediately loads the current bundle.
- After this release, leave a SPARC tab open across a later deployment. Within 60 seconds, or immediately after returning focus to the tab, SPARC should reload onto the new build automatically.
- A Leadership View Only row in Admin Users should display `All Program Areas`.
- Signing out from Admin and signing in as `sparc.tester1@tnedu.gov` should land on Dashboard with no Admin navigation button.

## Working Agreement

Bryan expects Codex to verify stage from observable deployment evidence rather than assume a successful GitHub build means every browser is current. Testable work must be documented, committed, pushed to `develop`, and followed through to the stage SHA. Frontend changes require short interface version bumps, and future UI reports should distinguish server deployment state from long-lived client bundle state.
