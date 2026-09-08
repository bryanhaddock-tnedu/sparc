# SPARC-3 task cost breakdown simplification retro

## Summary

Florie's UAT feedback showed that the estimated ticket cost and variance fields were creating distrust. The calculation was technically following the configured model, but the resulting numbers looked too high for normal 3- and 5-point ticket examples. For the current SPARC-3 MVP, the Product Detail receipt should therefore focus on the reliable number SPARC can explain cleanly today: actual labor cost from Jira logged hours and approved rates.

## What changed

- Renamed the Product Detail section from `Task Level Forecast Breakdown` to `Task Level Cost Breakdown`.
- Updated the section helper text to describe tickets with actual labor cost by fiscal month.
- Removed visible `Estimated Cost` from each ticket card.
- Removed visible `Variance` from each ticket card.
- Kept ticket number, work type, summary, story point/Jira Team context, actual hours, and actual labor cost visible.
- Updated the product brief to document that estimated cost and variance are intentionally omitted until stakeholders validate a revised estimation model.
- Follow-up on 2026-09-08 added visible Actual Hours to each receipt card so Jira time-tracking totals can be reconciled against SPARC's accepted worklog hours before comparing dollars.

## What stayed the same

- Actual cost still comes from logged Jira hours multiplied by approved SPARC bill rates.
- Epics remain excluded from the normal task list once Jira issue type is synced.
- Jira Team Estimation Profiles remain Admin-maintained configuration for future estimate-model work, but their outputs are not shown in the current Product Detail receipt view.
- No contributor names, role-level worklog breakdowns, or bill rates are exposed in the receipt cards.

## Versioning

- Frontend/interface version: `0.1.114` to `0.1.115`
- Root release version: `0.1.77` to `0.1.78`
- Follow-up frontend/interface version: `0.1.115` to `0.1.116`
- Follow-up root release version: `0.1.78` to `0.1.79`

## Verification

- Backend focused regression: `104 passed` across `tests/test_services.py` and `tests/test_access_control_enforcement.py`.
- Frontend TypeScript/Vite production build passed with interface version `0.1.115`.
