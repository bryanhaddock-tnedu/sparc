# SPARC Retrospective - 2026-07-14 13:08

## Retrospective Metadata

- Date: 2026-07-14
- Project: SPARC - Staff Planning and Resource Control
- Milestone / Session: Jira roadmap hierarchy diagnosis and descendant Actual rollup
- Participants: Bryan Haddock and Codex acting as SPARC engineering partner
- Branch: `develop`
- Handoff target: Bryan, Florie, and future SPARC Codex agents

## Request And Diagnosis

Florie clarified the intended Jira lineage:

```text
Roadmap Item / Jira Product Discovery Idea
  -> Deliverable
    -> Epic
      -> User Story or other descendant work item
        -> Jira worklog / Actual hours
```

The reported symptom was that roadmap sync appeared to work for some items but not all. Investigation separated two materially different failure classes:

1. Roadmap Item is absent from SPARC entirely.
   - Current inclusion requires the configured roadmap project, exact Jira issue type `Idea`, exact fiscal-year label such as `FY27`, and visibility to the Jira integration account.
   - Product mapping does not decide whether an Idea is fetched; it affects attribution after import.
2. Roadmap Item is present, but descendant Actual hours do not roll up.
   - The existing roadmap sync stored only Jira work items directly linked to the Idea.
   - The worklog sync stores the exact Jira ticket on which time was logged.
   - No Jira `parent` hierarchy was fetched, so a worklog on a Story could not match the directly linked Deliverable.

The second failure class was confirmed directly in the current implementation and fixed in this milestone. Exact working/failing Jira keys are still useful for validating whether Florie's observed examples also include the first class.

## Implementation

- Roadmap sync still begins with fiscal-year-scoped Jira Product Discovery Ideas.
- Direct Idea delivery links are still preserved.
- For each direct delivery link, SPARC now queries Jira children through the `parent` relationship recursively, up to six levels.
- Descendant Epics, Stories, Tasks, and subtasks are stored as `RoadmapItemIssueLink` records tied to the same Roadmap Item.
- Each descendant link retains its immediate parent Jira key in `relationship_type`, for example `Child of APP-20`.
- Duplicate descendants are deduplicated by Jira key.
- Shared or conflicting Roadmap Item ancestry remains visible as an ambiguous mapping instead of silently selecting one Roadmap Item.

## Data Guardrails Preserved

- Forecast remains SPARC-owned at Product + Team Member + Bucket + Fiscal Month + Fiscal Year.
- Roadmap hierarchy does not create, overwrite, or change Forecast rows.
- Worklog sync remains the source of Actual hours.
- Actual rows retain the Jira ticket where the worklog was entered.
- Roadmap sync only adds read-only association context used to attribute the original Actual ticket to a Roadmap Item.
- Product Program Area remains `Product.office` for access control. Jira Roadmap Item metadata is not an authorization boundary.

## Interface And Documentation

- The Jira Sync completion notice now says `linked Jira work items` because the count includes direct delivery work and hierarchy descendants.
- Product brief and roadmap billing milestones now document recursive Jira hierarchy attribution.
- Root version advanced to `0.1.52`.
- Frontend/interface version advanced to `0.1.89`.
- Version strings remain deliberately short because long version or migration identifiers have broken stage deployment previously.

## Verification

- Focused roadmap hierarchy tests: 2 passed.
- Full backend suite: 103 passed.
- Frontend production build: passed.
- `git diff --check`: passed.
- The frontend build retained the existing large-chunk warning; this is not introduced by the roadmap change.

Regression coverage now proves:

- A direct Deliverable is discovered and enriched.
- Its Epic child is discovered through Jira `parent`.
- The Epic's Story child is discovered through Jira `parent`.
- Actual hours logged on the Story resolve to the correct parent Roadmap Item without rewriting the Actual ticket key.

## Stage Validation

After deployment:

1. Sign in as Admin and open Admin > Jira Sync.
2. Select the applicable fiscal year and run Sync Roadmap.
3. Confirm the completion notice reports Roadmap Items and linked Jira work items.
4. Locate a Roadmap Item whose time is logged on a descendant Story.
5. Run or wait for Jira Actuals sync.
6. Confirm the Story no longer appears in Roadmap Actual Gaps and its hours appear under the expected Roadmap Item.
7. Confirm any Roadmap Item absent entirely has the exact `Idea` type and fiscal-year label in Jira and is visible to the integration account.

For a conclusive comparison, capture one Jira Roadmap key that works and one that fails, plus whether the failure is an absent Roadmap Item or present item with missing hours.

## Collaboration Notes

- Bryan expects implementation to proceed when stakeholder intent is clear, with interruptions only for real blockers.
- He wants concise progress updates in conversation and detailed durable context in committed retrospectives.
- Testable milestones should be documented, committed, and pushed to `develop` so GitHub triggers the stage deployment.
- Stage, not local UI, is the stakeholder validation environment; Docker is appropriate for engineering regression tests.

