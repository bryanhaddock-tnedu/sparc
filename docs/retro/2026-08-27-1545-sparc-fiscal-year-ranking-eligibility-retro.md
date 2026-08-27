# SPARC Fiscal-Year Ranking Eligibility Retrospective

## Retrospective Metadata

- Date: 2026-08-27
- Project: SPARC
- Milestone / Session: Team Member Ranking fiscal-year relevance
- Participants: Bryan Haddock and Codex
- Branch: `develop`
- Interface version: `0.1.104` to `0.1.105`
- Root release version: `0.1.67` to `0.1.68`

## Session Summary

Bryan identified the issue in UAT at `https://sparc.uat.tnedu.gov/teams/product-maintenance`: with FY2027 selected, inactive Team Member Dean Bowles appeared in the Team Member Rankings despite having zero Forecast and zero FYTD Actual hours. The ranking builder included every rostered Team Member and displayed zeroes for members with no selected-fiscal-year activity.

The ranking eligibility rule now keeps active Team Members visible for forward planning while including inactive Team Members only when they have nonzero Forecast or Actual work in the selected Fiscal Year. This preserves historical fiscal-year context without carrying former staff into later fiscal-year rankings where they have no work.

## Technical Outcomes

- Updated `buildTeamMemberRankingRows` to filter inactive members unless selected-fiscal-year Reported Values contain nonzero Forecast or Actual hours.
- Applied the same shared eligibility rule to Team Management and Team Analytics rankings.
- Updated ranking copy to describe eligible Team Members and fiscal-year-aware behavior.
- Added the durable product-brief rule for all-Team and team-specific ranking tables.
- Bumped the frontend interface version to `0.1.105` and root release version to `0.1.68` so deployed browsers refresh their assets.

## Verification

- `git diff --check` passed.
- The change was reviewed against the UAT case: an inactive member with zero FY2027 Forecast and Actual values is now excluded; active roster members remain visible even before work is entered; inactive members remain visible in fiscal years with Forecast or Actual history.
- A clean Node 22 container build was attempted, but Docker Desktop lost its daemon connection while `npm install` was running. The build must be rerun successfully before stage acceptance.

## Handoff Notes

- Current state: implementation, product brief, and version updates are ready on `develop` for commit and push.
- Recommended next step: rerun the Node 22 frontend build, commit, push `develop`, wait for UAT deployment, then confirm Dean Bowles is omitted from Product Maintenance rankings for FY2027 and appears only in fiscal years with Forecast or Actual history.
- Important context: UAT deploys automatically from the default `develop` branch.
