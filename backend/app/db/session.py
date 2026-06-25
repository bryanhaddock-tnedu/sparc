from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.entities import Base
from app.services.slugs import slugify

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def create_database() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_database_compatibility()


def drop_database() -> None:
    Base.metadata.drop_all(bind=engine)


def ensure_database_compatibility() -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "products" not in table_names:
        return

    dialect = "postgresql" if engine.dialect.name.startswith("postgresql") else "sqlite"
    with engine.begin() as connection:
        product_columns = {column["name"] for column in inspector.get_columns("products")}
        if "budget_amount" not in product_columns:
            product_budget_sql = {
                "postgresql": "ALTER TABLE products ADD COLUMN IF NOT EXISTS budget_amount NUMERIC(12, 2) NOT NULL DEFAULT 0",
                "sqlite": "ALTER TABLE products ADD COLUMN budget_amount NUMERIC(12, 2) NOT NULL DEFAULT 0",
            }
            connection.execute(text(product_budget_sql[dialect]))
        product_org_column_sql = {
            "office": {
                "postgresql": "ALTER TABLE products ADD COLUMN IF NOT EXISTS office VARCHAR(80)",
                "sqlite": "ALTER TABLE products ADD COLUMN office VARCHAR(80)",
            },
            "division": {
                "postgresql": "ALTER TABLE products ADD COLUMN IF NOT EXISTS division VARCHAR(160)",
                "sqlite": "ALTER TABLE products ADD COLUMN division VARCHAR(160)",
            },
        }
        for column_name, statements in product_org_column_sql.items():
            if column_name in product_columns:
                continue
            connection.execute(text(statements[dialect]))
            product_columns.add(column_name)
        if "slug" not in product_columns:
            product_slug_sql = {
                "postgresql": "ALTER TABLE products ADD COLUMN IF NOT EXISTS slug VARCHAR(180)",
                "sqlite": "ALTER TABLE products ADD COLUMN slug VARCHAR(180)",
            }
            connection.execute(text(product_slug_sql[dialect]))
            product_columns.add("slug")
        _backfill_product_slugs(connection)
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_products_slug ON products (slug)"))

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "product_budgets" in table_names:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO product_budgets (product_id, fiscal_year, budget_amount, created_at, updated_at)
                    SELECT p.id, 2026, p.budget_amount, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    FROM products p
                    WHERE p.budget_amount IS NOT NULL
                      AND p.budget_amount > 0
                      AND NOT EXISTS (
                        SELECT 1
                        FROM product_budgets pb
                        WHERE pb.product_id = p.id AND pb.fiscal_year = 2026
                      )
                    """
                )
            )

    if "team_members" in table_names:
        inspector = inspect(engine)
        team_member_columns = {column["name"] for column in inspector.get_columns("team_members")}
        with engine.begin() as connection:
            if "slug" not in team_member_columns:
                team_member_slug_sql = {
                    "postgresql": "ALTER TABLE team_members ADD COLUMN IF NOT EXISTS slug VARCHAR(180)",
                    "sqlite": "ALTER TABLE team_members ADD COLUMN slug VARCHAR(180)",
                }
                connection.execute(text(team_member_slug_sql[dialect]))
            _backfill_team_member_slugs(connection)
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_team_members_slug ON team_members (slug)"))

    if "actual_entries" not in table_names:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("actual_entries")}
    actual_entry_column_sql = {
        "sync_run_id": {
            "postgresql": "ALTER TABLE actual_entries ADD COLUMN IF NOT EXISTS sync_run_id INTEGER",
            "sqlite": "ALTER TABLE actual_entries ADD COLUMN sync_run_id INTEGER",
        },
        "source_issue_id": {
            "postgresql": "ALTER TABLE actual_entries ADD COLUMN IF NOT EXISTS source_issue_id VARCHAR(120)",
            "sqlite": "ALTER TABLE actual_entries ADD COLUMN source_issue_id VARCHAR(120)",
        },
        "source_account_id": {
            "postgresql": "ALTER TABLE actual_entries ADD COLUMN IF NOT EXISTS source_account_id VARCHAR(160)",
            "sqlite": "ALTER TABLE actual_entries ADD COLUMN source_account_id VARCHAR(160)",
        },
        "source_project_key": {
            "postgresql": "ALTER TABLE actual_entries ADD COLUMN IF NOT EXISTS source_project_key VARCHAR(80)",
            "sqlite": "ALTER TABLE actual_entries ADD COLUMN source_project_key VARCHAR(80)",
        },
        "source_payload_hash": {
            "postgresql": "ALTER TABLE actual_entries ADD COLUMN IF NOT EXISTS source_payload_hash VARCHAR(128)",
            "sqlite": "ALTER TABLE actual_entries ADD COLUMN source_payload_hash VARCHAR(128)",
        },
        "is_team_member_time": {
            "postgresql": "ALTER TABLE actual_entries ADD COLUMN IF NOT EXISTS is_team_member_time BOOLEAN NOT NULL DEFAULT true",
            "sqlite": "ALTER TABLE actual_entries ADD COLUMN is_team_member_time BOOLEAN NOT NULL DEFAULT 1",
        },
    }
    with engine.begin() as connection:
        for column_name, statements in actual_entry_column_sql.items():
            if column_name in existing_columns:
                continue
            connection.execute(text(statements[dialect]))


def _backfill_product_slugs(connection) -> None:
    products = connection.execute(text("SELECT id, name, slug FROM products ORDER BY id")).mappings().all()
    used: set[str] = set()
    for product in products:
        current_slug = product["slug"]
        slug = current_slug.strip() if isinstance(current_slug, str) and current_slug.strip() else slugify(product["name"], fallback="product")
        base_slug = slug
        suffix = 2
        while slug in used:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        used.add(slug)
        if slug != current_slug:
            connection.execute(text("UPDATE products SET slug = :slug WHERE id = :id"), {"slug": slug, "id": product["id"]})


def _backfill_team_member_slugs(connection) -> None:
    members = connection.execute(text("SELECT id, name, slug FROM team_members ORDER BY id")).mappings().all()
    used: set[str] = set()
    for member in members:
        current_slug = member["slug"]
        slug = current_slug.strip() if isinstance(current_slug, str) and current_slug.strip() else slugify(member["name"], fallback="team-member")
        base_slug = slug
        suffix = 2
        while slug in used:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        used.add(slug)
        if slug != current_slug:
            connection.execute(text("UPDATE team_members SET slug = :slug WHERE id = :id"), {"slug": slug, "id": member["id"]})


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
