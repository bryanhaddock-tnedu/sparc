import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import TeamMember

STAFF_ID_PREFIX = "SPARK"


def normalize_name(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_status(value: str | None) -> str:
    normalized = (value or "active").strip().lower()
    if normalized not in {"active", "inactive"}:
        raise ValueError("Status must be active or inactive")
    return normalized


def generate_staff_id(db: Session) -> str:
    staff_ids = db.scalars(select(TeamMember.staff_id).where(TeamMember.staff_id.is_not(None))).all()
    next_number = 1
    pattern = re.compile(rf"^{STAFF_ID_PREFIX}-(\d+)$")
    for staff_id in staff_ids:
        match = pattern.match(staff_id or "")
        if match:
            next_number = max(next_number, int(match.group(1)) + 1)
    while True:
        candidate = f"{STAFF_ID_PREFIX}-{next_number:03d}"
        if db.scalar(select(TeamMember.id).where(TeamMember.staff_id == candidate)) is None:
            return candidate
        next_number += 1


def create_team_member(db: Session, payload: dict[str, object]) -> TeamMember:
    data = dict(payload)
    data["name"] = normalize_name(str(data["name"]))
    data["status"] = normalize_status(data.get("status") if isinstance(data.get("status"), str) else None)
    if not data.get("staff_id"):
        data["staff_id"] = generate_staff_id(db)
    member = TeamMember(**data)
    db.add(member)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ValueError("Team member staff ID or identity already exists") from exc
    return member


def update_team_member(db: Session, member: TeamMember, payload: dict[str, object]) -> TeamMember:
    data = dict(payload)
    if "name" in data and data["name"] is not None:
        data["name"] = normalize_name(str(data["name"]))
    if "status" in data and data["status"] is not None:
        data["status"] = normalize_status(str(data["status"]))
    if "bill_rate" in data and data["bill_rate"] is not None:
        data["bill_rate"] = Decimal(str(data["bill_rate"]))
    for key, value in data.items():
        setattr(member, key, value)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ValueError("Team member update conflicts with an existing record") from exc
    return member


def find_existing_member(db: Session, *, staff_id: str | None, name: str) -> TeamMember | None:
    if staff_id:
        by_staff_id = db.scalar(select(TeamMember).where(TeamMember.staff_id == staff_id))
        if by_staff_id is not None:
            return by_staff_id
    normalized_name = normalize_name(name).lower()
    members = db.scalars(select(TeamMember)).all()
    for member in members:
        if member.name.lower() == normalized_name:
            return member
    return None
