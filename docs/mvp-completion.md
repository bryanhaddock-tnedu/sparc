# SPARC MVP Completion Notes

> Historical snapshot: this document records the first MVP completion point and is not the current backlog or application status. Use `docs/build-milestones.md`, `docs/access-control-plan.md`, and `docs/roadmap-billing-milestones.md` for the living plan.

This document summarizes the MVP work completed after the initial scaffold. Live Jira/Rovo integration, SPARC-local authorization, stage deployment, and Roadmap billing were implemented after this snapshot.

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

## Out Of Scope At This Historical Point

- Live Jira/Rovo integration. Implemented after this snapshot.
- Authentication and authorization. SPARC-local users/roles are now implemented; Entra end-to-end configuration remains pending externally.
- Kubernetes manifests or deployment repo wiring.
- Bill rate versioning.
- Project-management features such as boards, due dates, Gantt charts, or sprint planning.

## Historical Next Recommendation

The recommendations below were written before live integration and authorization shipped. Their current disposition is:

1. CI image build/publish exists; backend test, migration, lint, browser, and stage smoke gates remain in the living backlog.
2. Stage registry, ingress, and PostgreSQL connectivity are operating; Entra secret configuration remains externally pending.
3. Deployment infrastructure ownership remains outside the current application repository.
4. Live app-owned Jira/Rovo sync is implemented and scheduled in stage.
