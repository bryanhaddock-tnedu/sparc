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
- `AUTH_ENABLED=true`
- `AUTH_USERNAME`
- `AUTH_PASSWORD`
- `AUTH_SESSION_SECRET`
- `AUTH_SESSION_MINUTES=720`
- `JIRA_SITE_URL`
- `JIRA_API_EMAIL`
- `JIRA_API_TOKEN`

Container constants for stage:

- `ENVIRONMENT=stage`
- `AUTO_CREATE_SCHEMA=false`
- `SEED_ON_STARTUP=false`

Authentication is intentionally basic for the first stage release. The app reads one username/password pair from environment variables and gives every authenticated user the same permissions. The password and session secret should come from Key Vault. Generate `AUTH_SESSION_SECRET` as a long random value; it is used only to sign the HTTP-only session cookie.

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

## Database Build

DevOps should provision the Azure PostgreSQL server and database before the SPARC container starts. SPARC does not require a hand-written `schema.sql` file; the application schema is created and upgraded through Alembic migrations checked into `backend/alembic/versions`.

Required database setup:

1. Create an Azure PostgreSQL database for SPARC.
2. Create/provide a database user with permission to create and alter tables, indexes, constraints, and the Alembic version table.
3. Store the SQLAlchemy connection string in Key Vault or the deployment secret store as `DATABASE_URL`.
4. Run the SPARC migration command against that database before starting the app:

```bash
alembic upgrade head
```

The app image already contains `alembic.ini` and the migration files. In Kubernetes, run the migration command as a one-off job using the same image and the same `DATABASE_URL` secret used by the app container.

The database should not be initialized with local/demo data. After first deployment, load SPARC-owned setup/planning data through the app's Admin Data import workflow, then run Jira Sync from the app to populate Jira-sourced actuals.

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
