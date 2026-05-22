# SPARC Deployment

SPARC uses two container shapes:

- Local development: split frontend/backend/postgres in `docker-compose.yml`
- Stage: one app container in `docker-compose.stage.yml`

The stage container builds the React app and packages it into the FastAPI image. FastAPI serves `/api/*`, health checks, and the static frontend from the same origin.

## Stage Environment

Stage should use Azure PostgreSQL and Key Vault-backed environment variables.

Key Vault / container environment values:

- `DATABASE_URL`
- `SPARC_FRONTEND_ORIGIN=https://<stage-sparc-url>`
- `SPARC_DEFAULT_FISCAL_YEAR=2027`
- `JIRA_SITE_URL`
- `JIRA_API_EMAIL`
- `JIRA_API_TOKEN`

Container constants for stage:

- `ENVIRONMENT=stage`
- `AUTO_CREATE_SCHEMA=false`
- `SEED_ON_STARTUP=false`

For local testing of the stage container, copy `stage.env.example` to `stage.env` and fill in local/test values:

```bash
docker compose --env-file stage.env -f docker-compose.stage.yml --profile migrate run --rm migrate
docker compose --env-file stage.env -f docker-compose.stage.yml up --build app
```

Do not commit `stage.env`; it is ignored by git.

Optional for `docker-compose.stage.yml`:

- `SPARC_PORT=8000`
- `SPARC_FRONTEND_ORIGIN=http://localhost:8000`
- `SPARC_DEFAULT_FISCAL_YEAR=2027`

The stage compose file builds the frontend for same-origin API calls, so `VITE_API_BASE_URL` is intentionally blank there.

## Migration Rule

Stage data lives in Azure PostgreSQL. Do not reset or seed stage with local/demo data.

Deploy flow:

1. Build the app image.
2. Run tests.
3. Run `alembic upgrade head` against the stage database.
4. Deploy the app container.

With the stage compose file:

```bash
docker compose -f docker-compose.stage.yml --profile migrate run --rm migrate
docker compose -f docker-compose.stage.yml up --build app
```

In Kubernetes, run the same migration command as a one-off job before rolling the app deployment.
