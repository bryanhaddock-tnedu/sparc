# AGENTS.md - SPARC

SPARC is the internal labor forecasting and cost intelligence app for this project.

Use the detailed product brief in `docs/product-brief.md` as the source of truth for product scope, terminology, pages, data rules, API expectations, and explicit non-goals.

Important constraints:

- Build SPARC as an internal labor forecasting and cost intelligence app, not a project management tool.
- Use Product, Team Member, Bucket, Forecast, Actual, and Fiscal Month as canonical terms.
- Do not add task boards, sprint planning, timelines, due dates, Gantt charts, Bootstrap, Kubernetes, authentication, or live Jira/Rovo integration unless explicitly requested.
- Jira/Rovo access must be app-owned and server-side. The AI should only invoke app codepaths, not direct Jira APIs.
