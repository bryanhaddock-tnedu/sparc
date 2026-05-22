# SPARC Retrospective - 2026-05-22 08:23

## Retrospective Metadata

- Date: 2026-05-22
- Project: SPARC - Staff Planning & Resource Cost Intelligence
- Milestone / Session: MVP acceleration, executive polish, FY2027 planning import, and deployment readiness
- Participants: Bryan Haddock and Codex acting as SPARC engineering partner
- Related files / branches / tickets:
  - Branch: `develop`
  - `docs/product-brief.md`
  - `docs/deployment.md`
  - `docker-compose.stage.yml`
  - `Dockerfile`
  - `backend/app/api/products.py`
  - `backend/app/services/forecasting.py`
  - `backend/app/services/aggregations.py`
  - `backend/app/services/jira_rovo.py`
  - `backend/app/services/jira_projects.py`
  - `frontend/src/pages/DashboardPage.tsx`
  - `frontend/src/pages/ProductDetailPage.tsx`
  - `frontend/src/pages/ProductSettingsPage.tsx`
  - `frontend/src/components/BudgetTracker.tsx`
  - `frontend/src/components/ProductSummaryTable.tsx`
  - `/Users/bhaddock/Downloads/TimeTracking_FiscalYear2027.xlsx`
- Handoff target bot or teammate: Future SPARC Codex sessions, Bryan, and DevOps reviewers

## Session Summary

- What did we work on?
  - We pushed SPARC from a scaffold/prototype toward a credible MVP for labor planning and cost intelligence.
  - We refined the dashboard, product detail pages, product settings, Jira mappings, fiscal-year handling, budget tracking, Product Team workflow, and FY2027 forecast import.
  - We also started shaping stage deployment expectations around a single app container plus Azure PostgreSQL.
- Why did this work matter?
  - SPARC is becoming a high-visibility tool quickly. It needs to feel trustworthy enough for leadership review while still being honest about what is real data, what is forecast, what is actual, and what is still manual setup.
  - The dashboard needs to help the boss understand the labor story quickly without turning into a planning grid.
- What was completed?
  - Dashboard KPI row was tightened.
  - Product Summary table became sortable with two-level sort priority, defaulting to FYTD cost.
  - Budget tracker now distinguishes budget, forecast, and actuals more clearly.
  - Product budget became fiscal-year specific.
  - Product Team removal now clears forecast lines while retaining Jira actuals.
  - Bad pasted July/August forecast imports were rolled back.
  - FY2027 July/August forecast was re-imported from the actual workbook using real Excel cell coordinates.
  - Stage deployment docs and single-container compose path were established.
- What remains in flight?
  - A real Forecast Import UI/page is still needed.
  - Jira live sync needs continued hardening, mapping review, and user-facing validation.
  - Product/team/budget setup flows need more guardrails before stage deployment.
  - The estimation work is intentionally back-burnered.

## Technical Outcomes

- What code or docs changed?
  - Backend product APIs now support product-team assignments, product Jira spaces, fiscal-year product budgets, and removal behavior that clears forecast rows.
  - Forecasting service upserts create Product Team assignments when forecast rows are created.
  - Aggregation logic supports fiscal-year-specific budget and dashboard/product summaries.
  - Frontend pages now include stronger dashboard navigation, compact KPI cards, sortable product summary, Product Team and Forecast Line sections, and clearer budget tracker visuals.
  - Deployment docs and stage compose configuration were added.
- What behaviors were added, removed, or fixed?
  - Added multi-factor sort to Product Summary.
  - Added workbook-based FY2027 July/August forecast import, using cell coordinates.
  - Fixed stale forecast rows remaining after removing a Product Team member.
  - Removed the bad pasted forecast import and its fallout Product Team assignments.
  - Improved no-actuals product detail visualization for future fiscal years.
- What architecture or design decisions were made?
  - SPARC should preserve Forecast, Actual, Estimated, and Reported as separate concepts.
  - Product Team is the set of people allowed/planned for a product; Forecast Lines define bucket-level planning rows.
  - Jira actuals are historical evidence and should not be deleted when a planning assignment is removed.
  - Budgets are fiscal-year specific.
  - Workbook import must be source-coordinate based and auditable, not based on copied chat text.
  - Stage/prod should use app-owned server-side Jira access and server-side secrets only.
- What technical constraints or unknowns came up?
  - Pasted spreadsheet matrices can silently shift columns and cannot be trusted for wide planning grids.
  - Local DB schema and stage DB schema need a careful migration path.
  - Azure Key Vault injection strategy is still a DevOps decision, though the app is ready for env-var style inputs.
  - Product/Jira mapping policy is evolving as real Jira projects are reviewed.

## Verification

- What did we test or validate?
  - Backend test suite passed after relevant changes: `29 passed`.
  - Frontend production build passed after UI changes.
  - Database verification queries confirmed FY2027 July and August forecast totals after workbook import:
    - July: 33 rows, 1,425 hours
    - August: 36 rows, 1,200 hours
  - Rollback verification confirmed only the intended pre-existing rows remained before workbook re-import.
  - Workbook extraction printed Excel cell coordinates for every imported forecast value.
- What was not tested?
  - Full browser walkthrough after every later import step.
  - Stage container running against Azure PostgreSQL.
  - Real Jira sync end-to-end in a stage environment.
  - Forecast import through a reusable app endpoint or UI, because import was done with an ad hoc backend script.
- What still feels risky?
  - Ad hoc data import scripts are too easy to get wrong and too hard to audit later.
  - Product Team assignments created by forecast imports need deliberate review so automated imports do not override manager intent.
  - The dashboard can look authoritative before all budgets/mappings are complete.
  - Stage deployment may expose gaps in migrations or environment variables.
- What evidence do we have that the current state works?
  - Tests pass.
  - Builds pass.
  - Database totals match workbook extraction.
  - The bad import was identified, backed out, and replaced using a safer method.

## Collaboration Review

- What parts of the collaboration worked especially well?
  - The user gave direct product feedback from real screens, which made UI decisions practical instead of theoretical.
  - Naming and concept correction happened quickly: SPARC, budget semantics, Product Team versus Forecast Lines, and Jira Sync wording.
  - The user caught incorrect imported data quickly, preventing bad planning data from becoming normalized.
- What kind of prompts or instructions helped most?
  - Screenshots with concrete complaints were extremely effective.
  - Explicit product rules were helpful, especially around Product Team behavior, fiscal years, budgets, and Jira mapping.
  - Providing the actual workbook allowed a correct import after the pasted data failed.
- What communication style was most effective?
  - Short implementation updates while working.
  - Direct acknowledgement when something was wrong.
  - Practical explanations of why a behavior occurred and what would be changed.
- Where did we lose momentum or create confusion?
  - The pasted spreadsheet import was handled too confidently. The data looked tabular but was not safe enough to import.
  - Budget versus forecast language needed several rounds to settle.
  - Product Team removal originally retained forecast rows because the model was preserving history, but the user expectation was operational cleanup.
- What should future bots know about how the user likes to work?
  - Bryan works quickly and iteratively, using real screens and real data to evaluate whether SPARC is useful.
  - He prefers practical, product-owner explanations over abstract architecture talk.
  - He wants mistakes acknowledged plainly, fixed decisively, and turned into process improvements.
  - He values credibility and auditability because SPARC is likely to be shown upward.

## Workflow Preferences Learned

- Preferred interaction style:
  - Collaborative, direct, and implementation-oriented.
  - Explain the why, but keep moving.
- Preferred pacing:
  - Fast progress with frequent short updates.
  - Pause only for decisions that genuinely affect data integrity or product direction.
- Preferred level of detail:
  - Enough detail to understand source, impact, and risk.
  - Avoid burying the user in implementation noise unless asked.
- Things that increase focus:
  - Screenshots.
  - Concrete examples from the app.
  - Exact fiscal year/month labels.
  - Clear distinction between forecast, actual, budget, and reported values.
- Things that create friction:
  - Ambiguous labels like "Ranked by product labor plan and actuals."
  - UI cards or warnings that reserve permanent space for low-value cleanup items.
  - Silent assumptions during data imports.
  - Any workflow that makes the user create products or mappings one by one unnecessarily.
- Good defaults for future sessions:
  - Verify real data imports before writing to DB.
  - Prefer preview-first workflows for imports and mappings.
  - Treat unknown Jira projects as unmapped, not as Core Infrastructure.
  - Use FY2027 as the active planning year unless the user says otherwise.
  - Keep the dashboard executive-focused, not grid-heavy.

## Friction And Weaknesses

- What slowed us down?
  - Reworking semantics after initial UI assumptions were visible in the app.
  - Fixing the bad pasted import and cleanup fallout.
  - Needing to infer real deployment expectations from brief DevOps guidance.
- What did the system make the user manage unnecessarily?
  - Product creation and product mapping were initially too manual.
  - Forecast import required Codex intervention instead of a user-facing upload/preview/confirm flow.
  - The app did not clearly protect the user from stale forecast rows after Product Team removal.
- What did the bot misunderstand?
  - It trusted pasted spreadsheet matrix data too much.
  - It initially treated removal from Product Team as a history-preserving action instead of an operational cleanup action.
  - It needed repeated guidance to make the dashboard tighter and less cluttered.
- What technical weaknesses showed up?
  - No import run/audit model for forecast workbook imports.
  - No rollback UI for forecast imports.
  - No validation preview table before writes.
  - Some backend operations still use ad hoc scripts for data management.
- What workflow weaknesses showed up?
  - The project is moving quickly enough that data operations need guardrails now, not later.
  - The app needs clearer "source of truth" cues in the UI, especially when real Jira data and manual forecasts coexist.

## Action Items

- [ ] Product / UX improvement: Build a Forecast Import page with upload, preview, totals, validation, confirmation, and rollback.
- [ ] Engine / logic improvement: Add a `ForecastImportRun` or similar audit table to store workbook name, sheet, month, row count, totals, imported-by context, and replaced rows.
- [ ] Documentation improvement: Document the fiscal-year forecast import rules and workbook expectations in `docs/product-brief.md` or a dedicated import doc.
- [ ] Collaboration improvement: For every nontrivial data import, show parsed rows and validation results before writing anything.
- [ ] Testing / validation improvement: Add tests for forecast import parsing, unknown names/products, bucket normalization, replacement mode, and rollback behavior.

## Open Questions

- What still needs clarification?
  - Should forecast imports always replace the selected month, or should append/update be selectable?
  - Should Product Team assignments be created automatically from imports, or should imports only create forecast lines for existing Product Team members?
  - Should actuals from Jira automatically create Product Team membership, or only mapping evidence?
- What decisions are deferred?
  - Estimation and reported/effective values are deferred until the core forecast/actual workflow is stable.
  - Authentication is still out of scope unless explicitly requested.
  - Final Key Vault versus app-loaded secret pattern is deferred to DevOps implementation details.
- What assumptions should be revisited later?
  - FY2027 is the active planning year.
  - Workbook tab names and layout will stay consistent enough for a parser.
  - Managers want Product Team removal to delete forecast lines but not Jira actuals.
  - Dashboard should prioritize executive overview over data-quality warning cards.

## Handoff Notes

- Current state:
  - SPARC has real roster/products/Jira mappings in local DB, workbook-loaded FY2027 July/August forecasts, dashboard improvements, Product Team/Forecast Line workflow, and stage deployment scaffolding.
  - The bad pasted import was removed and replaced by workbook-coordinate import.
- Recommended next step:
  - Build the proper Forecast Import UI and backend service so future forecast loads are safe, repeatable, previewable, and auditable.
- Things to avoid:
  - Do not import wide spreadsheet data from pasted chat text.
  - Do not silently map unknown Jira projects to Core Infrastructure.
  - Do not collapse forecast, actual, estimated, and reported/effective values.
  - Do not delete Jira actuals when changing planning assignments.
- Important context for the next bot:
  - The user cares deeply about SPARC becoming credible quickly.
  - The dashboard is for leadership summary, not planning entry.
  - Product Team membership and forecast bucket lines are separate but connected workflows.
  - The actual workbook import showed Kasey Franklin as `URS / Maintenance`, correcting the earlier pasted-data mistake.
- Commands or files the next bot should start with:
  - `sed -n '1,220p' docs/product-brief.md`
  - `sed -n '1,220p' docs/deployment.md`
  - `sed -n '1,260p' backend/app/services/forecasting.py`
  - `sed -n '1,340p' backend/app/api/products.py`
  - `sed -n '1,340p' frontend/src/pages/ProductDetailPage.tsx`
  - `docker compose exec backend pytest`
  - `docker compose exec frontend npm run build`
