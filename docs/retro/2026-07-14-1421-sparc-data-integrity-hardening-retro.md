# SPARC Retrospective - 2026-07-14 14:21

## Retrospective Metadata

- Date: 2026-07-14
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Full entity/interface integrity audit and remediation
- Participants: Bryan Haddock and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, Vijay, and future SPARC Codex agents

## Why This Work Happened

After the Roadmap hierarchy work, Bryan requested a read-only structural audit of every persisted entity and the interfaces that operate on them. The audit confirmed that the central labor model was sound, but it found several cross-boundary problems that could expose restricted labor data, allow competing mapping authorities, or erase planning history. Bryan then authorized remediation of those findings.

No redesign of SPARC's canonical grain was needed. Forecast remains Product + Team Member + Bucket + Fiscal Month/Fiscal Year. Actual, Forecast, Estimated, and Reported/Effective values remain separate.

## Resolved Findings

### Program Area Product Detail Exposure

Program Area users already had Dashboard hour redaction, but Product Detail endpoints still returned aggregate hours, bucket-hour distributions, and named Roadmap worklog rows.

Resolution:

- Product summary hour fields are nullable and are redacted server-side when `can_view_hours` is false.
- Bucket distribution requires explicit hour access.
- Product Roadmap actuals require both hour and named-person access.
- Product Detail does not request or render the hours chart or hour snapshot for Program Area users.
- Cost-only Product Detail remains available within assigned Product Program Areas.
- Focused route-dependency and service-redaction tests were added.

### Competing Jira Product Mapping Authorities

`ProductJiraSpace` and `JiraProductMapping` could both assign one Jira project to a Product. Product Settings wrote both tables, but the Integrations page could edit only the legacy table. Actual sync and estimation could then consume different answers.

Resolution:

- `ProductJiraSpace` is the sole Jira project-to-Product authority.
- `JiraProductMapping` remains only as a discovery/review cache for unmapped Jira projects.
- The Integrations Jira project table is read-only and directs mapping work to Product Settings.
- The legacy mapping update endpoint was removed.
- Actual sync always aligns discovery rows to the active canonical mapping and clears unsupported legacy assignments.
- Estimation no longer uses hard-coded or legacy Product fallbacks.
- Migration `0020_data_integrity` reconciles existing discovery rows to active canonical mappings.
- A regression test proves canonical mapping wins over a conflicting legacy row.

Expected assignments such as GOV/RPA to Core Infrastructure must now exist explicitly in Product Settings. Unknown projects stay unmapped.

### Destructive Product And Roster Lifecycle

Deleting a Product could cascade through Forecast, Actual, Estimate, and recommendation records. Removing a Product Team assignment explicitly deleted every matching Forecast row across fiscal years.

Resolution:

- Historical Product and Team Member ORM relationships no longer use delete-orphan cascades.
- Product deletion is blocked when Jira, Forecast, Actual, Estimate, recommendation, or Roadmap references exist.
- The API tells admins to mark such Products inactive.
- Removing a Product Team assignment with Forecast/Actual/Estimate history marks the assignment inactive and retains all history.
- Empty assignments can still be removed.
- Applied forecast recommendation links now use `ON DELETE SET NULL` so an audit decision does not become an accidental deletion blocker.

### Roadmap Mapping Ownership

Roadmap Product, Bucket, and Agency Office values were all manually editable, while Jira sync sometimes overwrote values and sometimes left stale values. There was no provenance.

Resolution:

- Roadmap Product and Bucket now have `manual` or `sync` mapping sources.
- Existing non-null mappings are migrated as manual to avoid silently clobbering stage decisions.
- Manual Product/Bucket mappings survive Jira sync.
- Clearing a manual override immediately returns the field to available Jira inference and marks it sync-owned.
- Jira Agency Office is synchronized exactly, including clearing stale values, and is read-only in SPARC.
- Interface labels say `Jira Agency Office` so this metadata is not confused with Product Program Area authorization.

### Retired Roadmap Forecast Persistence

The Roadmap planner had already been promoted to canonical `ForecastEntry` writes, but the old `RoadmapForecastAllocation` table/model and Product Roadmap summary code remained. The old table had been emptied by migration and usually produced zero summaries.

Resolution:

- The obsolete ORM entity, relationships, cleanup code, and Product Roadmap forecast summary fields were removed.
- Migration `0020_data_integrity` drops the obsolete table.
- The Team Roadmap planner still writes and reads canonical Product Forecast entries; its user workflow is unchanged.

### Admin Data Package Semantics

Admin Data represented itself too much like complete portability while omitting security identities, generated records, and audit history. It also exported the legacy Product mapping table.

Resolution:

- The page now explicitly says it is a portable setup package, not a database backup.
- Estimation Profiles are included as SPARC-owned portable configuration.
- Legacy Jira Product discovery mappings are no longer exported as configuration.
- Product/Jira imports synchronize the discovery cache from the canonical Product/Jira mapping.
- Product Program Area/Division imports use the same organization validation as Product Settings.
- Exclusions explicitly identify credentials/Entra links, Program Area grants, Jira/Roadmap refresh data, generated estimates, sync history, and recommendation audit history.

### Inactive Product Semantics

`Product.is_active` previously had little operational effect.

Resolution:

- Inactive Products remain readable in historical dashboards/reports.
- New Forecast writes are rejected.
- Jira Actual fetch, estimation mapping, and Roadmap Product inference ignore inactive Products.
- Stale-worklog cleanup only operates on currently active Product/Jira project scope, so retiring a mapping or Product does not erase historical Actuals.

### Schema Drift

The applied migrations and ORM metadata disagreed on AppUser/Jira catalog uniqueness and Roadmap indexes.

Resolution:

- ORM constraints and indexes now match the applied PostgreSQL schema.
- Migration revision ID `0020_data_integrity` is 19 characters, safely below the 32-character deployment limit.
- A real PostgreSQL upgrade through every migration completed.
- `alembic check` reports: `No new upgrade operations detected.`

## Verification

- Full backend suite after implementation: 109 tests passed.
- Frontend production build: passed.
- Full PostgreSQL Alembic migration chain through `0020_data_integrity`: passed.
- PostgreSQL `alembic check`: passed with no metadata drift.
- Python compile check: passed.
- `git diff --check`: passed during implementation and is rerun before commit.
- Existing Vite large-chunk warning remains; this work did not introduce it.

## Versioning

- Root package version: `0.1.53`.
- Frontend/interface version: `0.1.90`.
- Packaged app version file: `0.1.90`.
- Version and migration identifiers remain short because overlong identifiers previously broke stage deployment.

## Stage Validation

1. Sign in as a Program Area View Only user and open an assigned Product.
2. Confirm Product Detail shows cost context but no hour chart, hour snapshot, named Team Member rows, or Roadmap worklog details.
3. Sign in as Admin and confirm full Product Detail remains available.
4. In Product Settings, confirm each Jira project is mapped to exactly one Product.
5. In Jira Sync, confirm Discovered Jira Projects is read-only and reflects Product Settings.
6. Set a Roadmap Product or Bucket override, run Roadmap sync, and confirm the override remains.
7. Clear the override and confirm Jira-derived mapping resumes.
8. Remove a Product Team member with Forecast history and confirm the assignment becomes inactive while Forecast values remain.
9. Attempt to delete a Product with history and confirm SPARC directs the admin to mark it inactive.
10. Export Admin Data and confirm Estimation Profiles are available and the page states that the package is not a database backup.

## Remaining External Dependency

Entra App Registration and stage secret configuration remain external dependencies for end-to-end SSO. The local user/role/Program Area model and authorization logic do not depend on Entra and remain testable with local accounts.

## Collaboration Expectations For Future Agents

- Bryan wants work to continue decisively when stakeholder intent is clear; interrupt only for a real blocker or a decision with material product consequences.
- Retrospectives are required durable handoff material, not optional notes.
- When a change is testable, update the documentation, commit it, and push `develop` so GitHub triggers the stage deployment.
- Stage is the stakeholder validation environment. Docker is appropriate for engineering verification.
- Preserve existing data structures and canonical grains. Do not let Roadmap/Jira context become a second Forecast or authorization authority.
- Keep frontend and migration version strings short and bump the interface version for every frontend change.
