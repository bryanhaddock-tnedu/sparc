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
- `ENTRA_ENABLED=false` until the stage Entra app registration secret is available
- `ENTRA_TENANT_ID`
- `ENTRA_CLIENT_ID`
- `ENTRA_CLIENT_SECRET`
- `ENTRA_REDIRECT_URI=https://sparc.uat.tnedu.gov/api/auth/entra/callback`
- `ENTRA_POST_LOGOUT_REDIRECT_URI=https://sparc.uat.tnedu.gov/`
- `JIRA_SITE_URL`
- `JIRA_API_EMAIL`
- `JIRA_API_TOKEN`
- `JIRA_AUTO_SYNC_ENABLED=true`
- `JIRA_AUTO_SYNC_TIME=07:30`
- `JIRA_AUTO_SYNC_TIMEZONE=America/Chicago`

Container constants for stage:

- `ENVIRONMENT=stage`
- `AUTO_CREATE_SCHEMA=false`
- `SEED_ON_STARTUP=false`

Authentication uses SPARC-owned sessions. The `sparc` username/password remains a break-glass Admin login from environment variables, while app-created users can sign in with email plus temporary local password before SSO is enabled. After `ENTRA_ENABLED=true`, Microsoft Entra handles authentication and SPARC links the Entra identity to an existing active SPARC user by tenant/object ID or first-time email match. Roles and Program Area assignments remain managed inside SPARC. The password, Entra client secret, and session secret should come from Key Vault. Generate `AUTH_SESSION_SECRET` as a long random value; it is used only to sign HTTP-only SPARC session and Entra state cookies.

Optional Entra override:

- `ENTRA_AUTHORITY_URL=https://login.microsoftonline.com/<tenant-id>`

If omitted, SPARC uses the standard Microsoft tenant authority built from `ENTRA_TENANT_ID`. SPARC requests only `openid`, `profile`, and `email` scopes and does not require Microsoft Graph application permissions or Entra app roles.

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
- `SPARC_BUILD_VERSION=<git-sha-or-release-version>`

The stage compose file builds the frontend for same-origin API calls, so `VITE_API_BASE_URL` is intentionally blank there.

## Daily Jira Actuals Sync

SPARC runs the live Jira Actuals sync automatically from the app container once every morning. By default, the scheduler runs at `07:30` in `America/Chicago`, which keeps the sync before 8am Central time. The scheduler uses the same server-side Jira integration code as the Admin Jira Sync button and only syncs the current fiscal year.

The automatic run skips when Jira credentials are missing or when a live Jira sync already ran on the same Central-time date. Manual sync remains available from Admin.

## Frontend Versioning

Every user interface change should bump the JavaScript/interface version before pushing to `develop` for STAGE. Update these together:

- `package.json`
- `frontend/package.json`
- `frontend/public/app-version.json`

The frontend embeds the package version when `VITE_BUILD_VERSION` is unset or `local`. The packaged FastAPI app also exposes `frontend/public/app-version.json` through `/api/app-version` when no explicit `SPARC_BUILD_VERSION` is provided, which lets browser sessions detect a newer UI build and reload instead of staying on stale JavaScript.

## Migration Rule

Stage data lives in Azure PostgreSQL. Do not reset or seed stage with local/demo data.

Alembic revision identifiers must stay short enough for the default `alembic_version.version_num` column. Keep every migration `revision` and `down_revision` value at or below 32 characters, for example `0019_access_users`. Do not use long generated names as revision IDs. The regression test in `backend/tests/test_migrations.py` enforces this because overlong revision IDs have broken stage deployment before.

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
