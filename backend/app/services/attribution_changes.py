from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AttributionChange
from app.services.access_control import AuthenticatedUser
from app.services.costs import round_hours


def record_attribution_change(
    db: Session,
    *,
    change_type: str,
    source_key: str,
    from_value: str | None,
    to_value: str | None,
    affected_actual_count: int,
    affected_hours: Decimal | float | int,
    affected_cost: Decimal | float | int,
    actor: AuthenticatedUser | None,
    reason: str | None = None,
) -> AttributionChange:
    change = AttributionChange(
        change_type=change_type,
        source_key=source_key,
        from_value=from_value,
        to_value=to_value,
        affected_actual_count=affected_actual_count,
        affected_hours=Decimal(str(affected_hours)).quantize(Decimal("0.01")),
        affected_cost=Decimal(str(affected_cost)).quantize(Decimal("0.01")),
        changed_by_user_id=actor.id if actor else None,
        changed_by_display_name=actor.display_name if actor else "System",
        changed_by_email=actor.email if actor else None,
        reason=_clean_optional(reason),
    )
    db.add(change)
    db.flush()
    return change


def list_attribution_changes(db: Session, *, limit: int = 50) -> list[dict[str, object]]:
    bounded_limit = max(1, min(limit, 200))
    changes = db.scalars(select(AttributionChange).order_by(AttributionChange.created_at.desc(), AttributionChange.id.desc()).limit(bounded_limit)).all()
    return [serialize_attribution_change(change) for change in changes]


def serialize_attribution_change(change: AttributionChange) -> dict[str, object]:
    return {
        "id": change.id,
        "change_type": change.change_type,
        "source_key": change.source_key,
        "from_value": change.from_value,
        "to_value": change.to_value,
        "affected_actual_count": change.affected_actual_count,
        "affected_hours": round_hours(change.affected_hours),
        "affected_cost": round(float(change.affected_cost), 2),
        "changed_by_user_id": change.changed_by_user_id,
        "changed_by_display_name": change.changed_by_display_name,
        "changed_by_email": change.changed_by_email,
        "reason": change.reason,
        "created_at": change.created_at,
    }


def _clean_optional(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None
