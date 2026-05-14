from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.entities import Base

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


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
