# SPARC Retrospective - 2026-07-09 16:57

## Retrospective Metadata

- Date: 2026-07-09
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Milestone 10 Entra SSO plumbing
- Participants: Bryan Haddock and Codex acting as SPARC engineering partner
- Related files / branches / tickets:
  - Branch: `develop`
  - `backend/app/api/auth.py`
  - `backend/app/services/auth.py`
  - `backend/app/services/entra_auth.py`
  - `backend/app/services/access_control.py`
  - `backend/app/config.py`
  - `backend/tests/test_auth.py`
  - `frontend/src/pages/LoginPage.tsx`
  - `docs/access-control-plan.md`
  - `docs/deployment.md`
  - `stage.env.example`
- Handoff target bot or teammate: Bryan, DevOps, Florie, and future SPARC Codex sessions

## Session Summary

- What did we work on?
  - We resumed the access-control milestone plan and implemented the first Entra SSO plumbing while preserving the existing `sparc` break-glass Admin login.
- Why did this work matter?
  - Bryan needs to create real SPARC users now, test roles before SSO is live, and then have those same records work after TDOE SSO is connected.
- What was completed?
  - Added config-gated Entra authorization-code login and callback routes.
  - Added signed Entra state cookies for callback verification.
  - Added Entra ID token validation scaffolding using Microsoft JWKS.
  - Added first-time Entra-to-SPARC linking by active user email, then persistent matching by Entra tenant/object ID.
  - Added frontend SSO sign-in affordance when Entra is configured.
  - Updated deployment docs and `stage.env.example`.
  - Bumped JavaScript/interface versions to root `0.1.48` and frontend `0.1.85`.
- What remains in flight?
  - The TDOE Entra App Registration values still need to be provided and set in stage secrets.
  - End-to-end Entra login cannot be validated until stage has tenant/client/secret/redirect configuration.
  - Logout currently clears the SPARC app session; Entra federated logout can be added later if product/security wants a full Microsoft sign-out.

## Technical Outcomes

- What code or docs changed?
  - Backend auth status now reports `entra_enabled`.
  - Entra login redirects to Microsoft only when SPARC auth and all required Entra settings are present.
  - Callback exchanges an authorization code, validates the ID token, maps to an existing active SPARC user, and sets the normal SPARC session cookie with `auth_type="entra"`.
  - The login page now shows a `Sign in with TDOE SSO` button when the backend says Entra is configured, while keeping the email/password form for temporary local passwords and the `sparc` break-glass account.
- What architecture or design decisions were reinforced?
  - Entra authenticates only.
  - SPARC continues to own roles, capabilities, Program Area assignments, redaction, and backend data scoping.
  - Users are SPARC app users, not Team Members.
  - Product Program Area remains `Product.office`; roadmap item program area metadata is not part of access control.

## Verification

- Focused auth tests: `docker compose run --rm backend pytest tests/test_auth.py` -> 8 passed.
- Full backend suite: `docker compose run --rm backend pytest` -> 91 passed.
- Frontend build: `docker run --rm -v /Users/bhaddock/Repositories/sparc:/app -w /app/frontend node:22-alpine sh -lc "npm run build"` -> passed.
- Backend image rebuild with new dependency: `docker compose build backend` -> passed and installed `PyJWT[crypto]`.
- Known warning: Vite still reports the existing large JavaScript chunk warning.

## Workflow Preferences Learned

- Bryan wants retros committed because they are working memory for future Codex sessions.
- Keep moving once the milestone plan is agreed, but call out real blockers and security-relevant decisions.
- Version strings must stay short; this session used simple patch versions and did not add migration IDs.

## Open Questions

- Should SPARC add an explicit Entra logout endpoint that redirects through Microsoft logout, or is clearing the SPARC session enough for stage?
- Should SSO local-login fallback stay available indefinitely for all Admin-created users, or should local login be disabled by default after Entra is stable?

## Handoff Notes

- Current state:
  - Code supports Entra SSO once stage env values are present.
  - Existing `sparc` login still works as break-glass Admin.
  - Admin-created users can still use email plus temporary password before SSO.
- Recommended next step:
  - Commit/push this milestone, then configure stage secrets when DevOps returns the App Registration details.
- Things to avoid:
  - Do not add Entra app roles for SPARC authorization.
  - Do not auto-create SPARC users from Entra claims.
  - Do not use `RoadmapItem.program_area` as the security boundary.
