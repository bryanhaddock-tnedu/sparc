# SPARC Production Data Transfer Hardening Retrospective

## Retrospective Metadata

- Date: 2026-07-30
- Project: SPARC
- Milestone / Session: Pilot operations and stage-to-production data transfer
- Participants: Bryan Haddock and Codex; production setup coordinated with DevOps
- Branch: `develop`
- Starting SHA: `10a522128054263213fa6184f20256deabd98c5c`
- Interface version: `0.1.103` to `0.1.104`
- Root release version: `0.1.66` to `0.1.67`

## Session Summary

DevOps provisioned a SPARC production environment. Bryan exported Admin Data from stage and imported it into production. The browser received an nginx `504 Gateway Time-out`, but production subsequently showed imported data. This exposed two weaknesses: the browser could not report whether the backend committed, and the portable package had not been revisited after Roadmap, access-control, and attribution features were added.

The intended contract was clarified:

- The Admin Data package moves current state created or associated inside SPARC.
- Jira-owned and generated rows are recreated independently in each environment through Jira Roadmap, Actuals, and estimation syncs.
- Full same-environment disaster recovery belongs to DevOps-managed PostgreSQL backup/restore, not the Admin Data package.

Codex did not access, change, delete, or rerun anything in production during this session.

## Production Incident Evidence

The stage package generated at `2026-07-30T20:38:28Z` contained:

| Data Set | Rows |
|---|---:|
| Buckets | 3 |
| Estimation Profiles | 0 |
| Team Members | 50 |
| Products | 33 |
| Product Budgets | 8 |
| Product Team Members | 150 |
| Product Jira Spaces | 39 |
| Jira User Mappings | 30 |
| Forecast Entries | 2,331 |

The package intentionally excluded Actuals, sync history, Jira catalog data, Roadmap refresh rows, generated estimates, App Users/access grants, recommendation decisions, attribution audit history, and the legacy Jira Product discovery cache.

Because the import API commits once after processing the selected package, a gateway timeout does not by itself imply partial database writes. Seeing imported Products, Team Members, or Forecasts indicates that the backend likely continued after nginx stopped waiting and reached the commit. Row-level validation errors can still produce a committed subset and must be checked through logs and database reconciliation.

## Technical Outcomes

### Portable Package V2

- Added a unique package ID, format version, generated timestamp, and per-dataset row counts to the manifest.
- Preserved import compatibility with older v1 zip, workbook, and JSON packages.
- Added import summary metadata and separate warnings from hard row failures.

### SPARC-Owned Roadmap Overlay

- Added `Roadmap Item Overrides`, containing only manual Product/Bucket overrides keyed by Roadmap source, fiscal year, and Jira Roadmap Item key.
- Added `Roadmap Ticket Mappings`, containing only manual ticket-to-Roadmap Item associations.
- Jira-fetched Roadmap Items and links remain excluded.
- Missing Roadmap targets are skipped with an explicit warning to run Jira Roadmap sync and import the Roadmap datasets again.

### Sanitized User Access

- Added optional `User Access Definitions`.
- Transfers email, display name, role, active state, and Program Area assignments.
- Never transfers password hashes, Entra tenant/object IDs, or login history.
- Matching target users retain their existing authentication fields.
- Newly imported definitions have local login disabled and no password or Entra link.
- Import refuses to disable or demote the final active SPARC Admin.

### Forecast Import Performance

- Replaced per-row Product, Team Member, Bucket, Fiscal Month, roster, and Forecast queries with cached natural-key resolution and one batched ORM flush.
- Preserved inactive Product Forecast history and missing Product Team assignment recovery.
- Added Team Member staff IDs to relationship exports while retaining backward compatibility with name-based v1 packages.

### Natural-Key Integrity

- A rollback-only PostgreSQL test against an already populated local database exposed that the v1 importer could fall back to source database numeric IDs.
- Those IDs are environment-specific and could identify unrelated target rows, causing cascading Product renames.
- Removed numeric-ID fallback from Product, Team Member, and Bucket resolution.
- Source IDs remain informational export columns only.
- Added a regression test proving that colliding source/target IDs cannot rename unrelated target Products.

### Interface And Documentation

- Admin Data now identifies Roadmap datasets as `After Roadmap Sync`.
- User Access Definitions are visibly optional.
- Import summaries display package metadata, expected package rows, warnings, and failures.
- Updated the product brief, deployment guide, and milestone tracker with the environment-transfer contract and production branch promotion rule.
- Recorded that the exact DevOps production branch name must be confirmed; it must never be inferred.

## Verification

- Python syntax compilation passed.
- Focused Admin Data tests: `3 passed`.
- Complete backend suite: `140 passed`.
- Clean Node 22 TypeScript/Vite production build passed for interface `0.1.104`.
- Real v1 stage package imported into an isolated database using the updated path:
  - all nine base datasets processed
  - `0` hard errors
  - base application processing totaled approximately `0.84s`
- Real v1 stage package completed a rollback-only import against local PostgreSQL in approximately `0.97s` with `0` errors and `0` warnings.
- Admin Data UI verified at desktop and 390px mobile widths.
- No horizontal page overflow was present.

## Production Convergence Checklist

1. Do not blindly rerun the original timed-out package.
2. Ask DevOps to preserve a production database restore point and inspect nginx/API logs for the original import.
3. Reconcile production against the original package counts above.
4. Deploy and stage-test package v2 from `develop`.
5. Generate a fresh v2 package from stage.
6. Confirm the exact production deployment branch name.
7. Promote the exact stage-tested SHA to the production branch.
8. Confirm migrations, readiness, backend SHA, and interface version in production.
9. Import base SPARC datasets.
10. Optionally import sanitized User Access Definitions.
11. Run Jira Roadmap sync.
12. Import Roadmap Item Overrides and Roadmap Ticket Mappings.
13. Run Jira Actuals sync.
14. Run estimation only when generated estimates are needed.
15. Reconcile Products, Program Areas, budgets, Forecast totals, mappings, Roadmap gaps, Actual totals, and role behavior.

## Collaboration Review

Bryan correctly stopped the workflow when the first explanation drifted toward treating omitted Jira data as a defect. The durable requirement is narrower and clearer: move SPARC-owned state; regenerate Jira-owned state. Future agents should distinguish environment promotion from full database disaster recovery before changing transfer behavior.

Bryan expects testable work to be verified, documented in a committed retrospective, pushed to `develop`, and followed through automatic stage deployment. Production requires a separate explicitly named branch and exact-SHA promotion after stage acceptance. Do not push to a guessed production branch.

## Open Questions

- What exact branch name does DevOps use for production deployment?
- Did the original production import report any row-level failures in backend logs?
- Do production counts match the original package counts?
- Which stage user definitions should be promoted to production, excluding test users?
- Does DevOps have an accepted PostgreSQL backup retention and restore-test runbook?

## Handoff Notes

- Current implementation is local on `develop` pending final review, commit, push, and stage acceptance.
- The original stage package is `/Users/bhaddock/Downloads/sparc-admin-data-20260730-203828.zip`.
- Do not delete or manually edit production records to correct the timeout.
- Do not run Roadmap overlays before Jira Roadmap sync.
- Do not copy password hashes or Entra identity links between environments.
- Wintermute MCP was not available to this Codex thread; tool discovery and the active tool registry returned no Wintermute tools.
