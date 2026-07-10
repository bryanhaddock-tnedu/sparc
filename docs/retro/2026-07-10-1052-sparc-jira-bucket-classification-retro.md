# SPARC Retrospective - 2026-07-10 10:52

## Retrospective Metadata

- Date: 2026-07-10
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Jira bucket-classification hardening
- Participants: Bryan Haddock and Codex acting as SPARC engineering partner
- Related files / branches / tickets:
  - Branch: `develop`
  - `backend/app/services/jira_rovo.py`
  - `backend/app/services/estimation_policy.py`
  - `backend/tests/test_import_and_sync.py`
  - `backend/tests/test_estimation_policy.py`
  - `docs/product-brief.md`
- Handoff target bot or teammate: Bryan, product leadership, and future SPARC Codex sessions

## Session Summary

- What did we work on?
  - We set Entra-registration-dependent work aside and continued with locally testable SPARC logic.
  - The immediate issue was whether SPARC silently maps Core Infrastructure or unknown Jira work type into the Net New bucket.
- Why did this work matter?
  - Product and bucket are separate concepts. A bad default can make Actuals look classified when Jira did not provide trustworthy work-type data.
- What was completed?
  - Confirmed there was no Core Infrastructure -> Net New default.
  - Removed the silent fallback that treated missing or unrecognized Jira work type as Maintenance.
  - Live Jira actuals now skip unclassified worklogs instead of importing them into Maintenance.
  - If a previously imported actual later becomes unclassified, live sync deletes that stale classified actual.
  - Estimation now excludes unclassified Jira issues instead of estimating them under Maintenance.
  - Product brief now says unknown work type must remain unclassified and require review.
- What remains in flight?
  - A future review queue or UI could make unclassified Jira work type easier to resolve.
  - Product leadership may still want a richer workflow for classifying unknown work types without editing Jira.

## Technical Outcomes

- What architecture or design decisions were reinforced?
  - Product mapping and Bucket mapping are independent.
  - `Core Infrastructure` is a Product concept, not a Bucket.
  - `Net New`, `Enhance`, and `Maintenance` are Bucket/work-type concepts.
  - Missing or unknown work type must not be silently classified.

## Verification

- Focused tests: `docker compose run --rm backend pytest tests/test_import_and_sync.py tests/test_estimation_policy.py` -> 25 passed.
- Full backend suite: `docker compose run --rm backend pytest` -> 99 passed.

## Handoff Notes

- Current state:
  - Unknown Jira work type does not default to Maintenance or Net New.
  - Unclassified Jira Actuals are skipped and counted in skipped/unmapped sync totals.
  - Unclassified estimation issues are excluded with an explicit reason and warning.
- Recommended next step:
  - Continue logic work that can be tested locally, while keeping Entra end-to-end validation parked until registration values exist.
- Things to avoid:
  - Do not reintroduce a bucket default for unknown Jira values.
  - Do not conflate Product labels such as Core Infrastructure with Bucket labels such as Net New.
