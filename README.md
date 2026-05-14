# SPARK

SPARK is Staff Planning & Resource Knowledge: an internal labor forecasting and cost intelligence app.

## Local Docker

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs
- PostgreSQL: localhost:5433

Useful local commands:

```bash
docker compose exec backend python -m app.cli reset-db
docker compose exec backend python -m app.cli seed-db
docker compose exec backend pytest
docker compose exec frontend npm run build
```

## Local Without Docker

Run PostgreSQL locally or use the Compose postgres service, then:

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

```bash
npm install --prefix frontend
npm --prefix frontend run dev
```

## Notes

- Product scope and constraints live in `docs/product-brief.md`.
- MVP milestones live in `docs/build-milestones.md`.
- MVP completion notes live in `docs/mvp-completion.md`.
- STAGE deployment direction lives in `docs/stage-environment-plan.md`.
- The MVP seeds FY2026 months from July 2025 through June 2026.
- Jira/Rovo sync is mocked and app-owned; credentials and live external calls are intentionally not implemented yet.
- STAGE is expected to run containerized on Kubernetes with Azure PostgreSQL and Key Vault-backed secrets.
- For STAGE, set `AUTO_CREATE_SCHEMA=false` and run `alembic upgrade head` against Azure PostgreSQL before the app starts.
