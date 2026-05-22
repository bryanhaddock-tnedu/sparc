from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Bucket
from app.services.estimation_policy import ensure_default_estimation_profile
from app.services.fiscal_year import ensure_fiscal_months

BUCKETS = [
    ("NET_NEW", "Net New"),
    ("ENHANCE", "Enhance"),
    ("MAINTENANCE", "Maintenance"),
]


def seed_database(db: Session) -> None:
    """Seed only reference data required for the app to function."""
    _seed_buckets(db)
    ensure_fiscal_months(db, 2027)
    ensure_default_estimation_profile(db)
    db.commit()


def _seed_buckets(db: Session) -> None:
    for code, name in BUCKETS:
        existing = db.scalar(select(Bucket).where(Bucket.code == code))
        if existing is None:
            db.add(Bucket(code=code, name=name))
    db.flush()
