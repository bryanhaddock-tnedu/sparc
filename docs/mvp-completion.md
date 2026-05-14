# SPARK MVP Completion Notes

This document summarizes the MVP work completed after the initial scaffold.

## Completed MVP Scope

- Foundation hardening:
  - Alembic baseline migration added.
  - Backend CLI added for `init-db`, `seed-db`, and `reset-db`.
  - Local startup schema creation and seeding are now configurable.
  - Health endpoints added for basic, liveness, and readiness checks.
  - Typed response schemas added for the primary API surfaces.
  - API errors are more consistent for bad request, not found, and conflict cases.

- Durable data and sync contracts:
  - Sync run history model added.
  - Actual entries now include stable source identity fields for issue, worklog, account, project, payload hash, and team-member-time flag.
  - Mock sync can update legacy rows by ticket/worklog fallback and then enrich them with stable source IDs.

- Roster management:
  - CSV/XLSX team member import service added.
  - Import validates required columns.
  - Import generates staff IDs when missing.
  - Import is idempotent by staff ID or normalized name.
  - Team Management includes roster upload, result counts, and row-level errors.

- Forecast planning:
  - Batch forecast upsert API added.
  - Product Detail forecast editing now uses a save/discard workflow.
  - Dirty and invalid forecast cells are visibly marked.
  - Actuals, cost, remaining, and variance remain read-only calculated values.

- Mock Jira/Rovo actuals:
  - Mock worklogs now include issue IDs, keys, summaries, statuses, project keys, authors, dates, buckets, and hours.
  - Sync history is recorded for mock sync runs.
  - Jira user and product mapping APIs added.
  - Integration page added for mock sync, mapping management, unmapped references, and sync history.

- Verification:
  - Backend test coverage expanded to import and mock sync behavior.
  - Frontend TypeScript production build passes.

## Still Out Of MVP Scope

- Live Jira/Rovo integration.
- Authentication and authorization.
- Kubernetes manifests or deployment repo wiring.
- Bill rate versioning.
- Project-management features such as boards, due dates, Gantt charts, or sprint planning.

## Next Recommended Build

Move next into pilot hardening:

1. Add CI pipeline jobs for backend tests, frontend build, and image builds.
2. Coordinate STAGE registry, namespace, ingress, and Key Vault integration details with DevOps.
3. Add deployment handoff artifacts or manifests once DevOps confirms ownership.
4. Replace mock Jira/Rovo with live app-owned Jira/Rovo sync after the mapping workflow is validated with stakeholders.
