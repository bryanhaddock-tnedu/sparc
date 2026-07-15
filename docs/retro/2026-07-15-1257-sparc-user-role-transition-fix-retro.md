# SPARC Retrospective - 2026-07-15 12:57

## Retrospective Metadata

- Date: 2026-07-15
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Program Area to Leadership role transition fix
- Participants: Bryan Haddock and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, and future SPARC Codex sessions

## Session Summary

Florie reported an `Internal Server Error` after changing an existing Program Area View Only user to Leadership View Only and clicking Save changes. The selected Program Area remained checked in the row when the role changed.

The failure was caused by a mismatch between the Admin UI payload and the assignment replacement implementation:

- The UI sent all row values on every save, including the user's existing Program Area selection.
- The backend cleared the assignment relationship and immediately appended a new assignment with the same `(user_id, program_area)` key.
- PostgreSQL could attempt the insert before the orphaned row was deleted, violating `uq_user_program_area_assignment` and returning a 500.
- The prior regression test did not represent this path because it changed the role while explicitly sending an empty Program Area list.

## Completed Work

- Made role semantics authoritative in the backend:
  - Only Program Area View Only users retain Program Area assignment rows.
  - Admin and Leadership View Only users receive all-area access from their role and store no area assignments.
  - Promotion from Program Area View Only clears obsolete assignments even if a stale checked area is submitted.
- Replaced destructive clear-and-reinsert assignment updates with a set-difference update:
  - Existing requested assignments are preserved.
  - Removed assignments are deleted.
  - Only genuinely new assignments are inserted.
- Made the Admin Users UI role-aware:
  - Selecting Admin or Leadership View Only clears the draft's Program Area selections.
  - The area checklist is replaced by `All Program Areas` for those roles.
  - Program Area View Only continues to support one or more explicit assignments.
- Strengthened tests to cover the exact payload Florie submitted and to prove unchanged assignment rows are preserved.
- Updated the product brief with the role/assignment invariant.
- Bumped root release version to `0.1.56` and frontend/interface version to `0.1.93`.

## Verification

- Focused auth suite: `docker compose run --rm backend pytest tests/test_auth.py -q` -> 12 passed.
- Full backend suite: `docker compose run --rm backend pytest -q` -> 113 passed.
- PostgreSQL-backed reproduction using the real unique constraint -> passed.
- Frontend production build: `docker run --rm -v "$PWD":/app -w /app/frontend node:22-alpine sh -lc "npm run build"` -> passed.
- Diff hygiene: `git diff --check` -> passed.
- No database migration was required.
- Frontend lint remains unavailable because the repository invokes ESLint 9 without an `eslint.config.*` file. This is an existing tooling gap; TypeScript compilation and the production build passed.

## Stage Validation

After stage reports the release commit:

1. Sign in as `sparc` and open Admin > Users.
2. Change an existing Program Area View Only user with at least one checked area to Leadership View Only.
3. Confirm the Program Areas cell immediately reads `All Program Areas`.
4. Click Save changes and confirm the success message appears instead of `Internal Server Error`.
5. Refresh the user list and confirm the role remains Leadership View Only and no explicit Program Areas return.
6. Sign in as that user and confirm all Products are visible, Reports is available, edit/admin controls are absent, and bill rates are not exposed.

## Handoff Notes

- SPARC app roles and Product/Team Member labor roles are separate concepts.
- `Product.office` remains the Program Area authorization boundary.
- `RoadmapItem.program_area` remains Jira context and is not an authorization boundary.
- The `sparc` local login remains the break-glass Admin account.
- Entra authenticates; SPARC owns authorization, roles, capabilities, and Program Area assignments.
- Preserve assignment rows when their values do not change. This avoids uniqueness-ordering failures and unnecessary audit churn.
- Regression tests for Admin saves must use the payload shape emitted by the UI, not a hand-simplified subset.

## Working Agreement

Bryan expects Codex to keep development moving without unnecessary interruptions, investigate issues through the complete data and interface path, test with Docker where useful, document each testable milestone in a committed retrospective, push `develop` so GitHub deploys stage, and verify the deployed commit before asking for stage validation. Frontend changes always require a short interface version bump; migration revision IDs must remain at or below 32 characters.
