# SPARC Retrospective - 2026-07-09 17:20

## Retrospective Metadata

- Date: 2026-07-09
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Milestone 11 access-control hardening
- Participants: Bryan Haddock and Codex acting as SPARC engineering partner
- Related files / branches / tickets:
  - Branch: `develop`
  - `backend/app/api/forecasts.py`
  - `backend/tests/test_access_control_enforcement.py`
  - `docs/access-control-plan.md`
- Handoff target bot or teammate: Bryan, Florie, DevOps, and future SPARC Codex sessions

## Session Summary

- What did we work on?
  - We continued the access-control milestone plan after Entra SSO plumbing and audited backend role/scope enforcement.
- Why did this work matter?
  - Program Area View Only is a security boundary. UI hiding is not enough; the API must not expose named Team Member detail to roles that should only see scoped aggregate views.
- What was completed?
  - Found and closed a backend gap where `GET /api/forecasts` was scoped by Product Program Area but still returned named Team Member fields.
  - Changed forecast detail rows to require named Team Member visibility.
  - Added regression tests for Program Area product scoping, person-level report denial, bill-rate redaction, and the forecast route dependency.
  - Added Milestone 11 to the access-control plan.
- What remains in flight?
  - A future product decision is still needed on whether Program Area View Only users should see aggregate hours, aggregate dollars, or both.
  - End-to-end stage testing with real role-specific users is still needed.

## Technical Outcomes

- What code or docs changed?
  - `backend/app/api/forecasts.py` now uses `require_named_people_access` for forecast detail rows.
  - `backend/tests/test_access_control_enforcement.py` captures the role/scope/redaction rules at the backend level.
  - `docs/access-control-plan.md` now includes Milestone 11: Access-Control Hardening.
- What architecture or design decisions were reinforced?
  - Product Program Area scope is still `Product.office`.
  - Forecast details are named labor-resource data and should not be available to Program Area View Only users.
  - Aggregate dashboards and non-person reports remain available to scoped Program Area users pending the final aggregate-hours decision.

## Verification

- Focused enforcement tests: `docker compose run --rm backend pytest tests/test_access_control_enforcement.py` -> 4 passed.
- Full backend suite: `docker compose run --rm backend pytest` -> 96 passed.
- Diff hygiene: `git diff --check` -> passed.

## Handoff Notes

- Current state:
  - Backend forecast detail rows no longer expose Team Member names to Program Area View Only users.
  - Access-control tests now cover the most important role/scope rules.
- Recommended next step:
  - Commit and push this hardening pass, then continue with stage validation or the aggregate-hours product decision.
- Things to avoid:
  - Do not rely on frontend hiding for access control.
  - Do not use `RoadmapItem.program_area` for authorization.
