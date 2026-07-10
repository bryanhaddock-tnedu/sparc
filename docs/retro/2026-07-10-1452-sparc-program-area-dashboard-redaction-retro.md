# SPARC Retrospective - 2026-07-10 14:52

## Retrospective Metadata

- Date: 2026-07-10
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Program Area dashboard redaction and Reports access
- Participants: Bryan Haddock and Codex acting as SPARC engineering partner
- Related files / branches / tickets:
  - Branch: `develop`
  - `backend/app/services/access_control.py`
  - `backend/app/services/aggregations.py`
  - `backend/app/api/reports.py`
  - `frontend/src/pages/DashboardPage.tsx`
  - `frontend/src/components/ProductSummaryTable.tsx`
  - `frontend/src/components/PageNav.tsx`
  - `frontend/src/App.tsx`
  - `docs/access-control-plan.md`
- Handoff target bot or teammate: Bryan, Florie, Vijay, and future SPARC Codex sessions

## Session Summary

- What did we work on?
  - We incorporated Florie's stage-testing feedback for Program Area View Only users.
- Why did this work matter?
  - Program Area users should see scoped Product cost context without receiving Enterprise Reports or dashboard hour quantities.
- What was completed?
  - Added `can_view_reports` to the SPARC-local capability map.
  - Blocked Reports API and XLSX export access for Program Area View Only users.
  - Hid the Reports nav item and guarded direct `/reports` frontend access.
  - Redacted dashboard hour fields server-side for users without `can_view_hours`.
  - Updated Dashboard UI to hide hour cards, hour ranking controls, Product Summary hour columns, and hour sort options for Program Area users.
  - Switched Program Area dashboard mix/ranking views to cost mode where hour mode would otherwise leak quantities.
- What remains in flight?
  - Product Detail views may need the same hours-redaction review if Program Area users should be allowed into detail pages long term.

## Technical Outcomes

- What code or docs changed?
  - `backend/app/services/access_control.py` now exposes `can_view_reports`.
  - `backend/app/api/reports.py` uses a reports-access dependency.
  - `backend/app/services/reporting.py` rejects report generation for roles without reports access.
  - `backend/app/services/aggregations.py` returns `None` for dashboard hour fields when the current user cannot view hours.
  - Dashboard response schemas and TypeScript types now allow nullable hour fields.
  - `frontend/src/pages/DashboardPage.tsx` renders cost-only dashboard views when hours are not allowed.
  - `frontend/src/components/ProductSummaryTable.tsx` removes hour columns and hour sort choices when hours are not allowed.
  - `docs/access-control-plan.md` documents that Program Area View Only cannot view Reports or dashboard hour quantities.
- What architecture or design decisions were reinforced?
  - UI hiding alone is not sufficient; backend API responses must also avoid returning restricted values.
  - Program Area View Only remains scoped by `Product.office`.
  - Cost visibility and hour visibility are separate capabilities.

## Verification

- Focused access-control tests: `docker compose run --rm backend pytest tests/test_access_control_enforcement.py` -> 5 passed.
- Full backend suite: `docker compose run --rm backend pytest` -> 101 passed.
- Frontend production build: `docker run --rm -v "$PWD":/app -w /app/frontend node:22-alpine sh -lc "npm run build"` -> passed.
- Diff hygiene: `git diff --check` -> passed.

## Handoff Notes

- Current state:
  - Program Area View Only users should no longer see Reports or dashboard hour values once stage deploys this commit.
- Recommended next step:
  - Validate on stage with Florie's Academics Program Area user after deployment.
- Things to avoid:
  - Do not re-enable Reports for Program Area users unless product explicitly changes the access model.
  - Do not return real hour values as hidden frontend-only data for roles without `can_view_hours`.
