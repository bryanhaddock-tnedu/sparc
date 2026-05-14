from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import bad_request, not_found
from app.db.session import get_db
from app.models import TeamMember
from app.schemas import TeamImportResult, TeamMemberCreate, TeamMemberProductsResponse, TeamMemberResponse, TeamMemberUpdate
from app.services.aggregations import serialize_team_member, team_member_products
from app.services.team_import import import_team_members
from app.services.team_members import create_team_member as create_member_service
from app.services.team_members import update_team_member as update_member_service

router = APIRouter(prefix="/team-members", tags=["team members"])


@router.get("", response_model=list[TeamMemberResponse])
def list_team_members(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    members = db.scalars(select(TeamMember).order_by(TeamMember.name)).all()
    return [serialize_team_member(member) for member in members]


@router.post("", response_model=TeamMemberResponse)
def create_team_member(payload: TeamMemberCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        member = create_member_service(db, payload.model_dump())
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc
    db.refresh(member)
    return serialize_team_member(member)


@router.post("/import", response_model=TeamImportResult)
async def import_team_member_file(file: UploadFile, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        result = import_team_members(db, filename=file.filename or "", content=await file.read())
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.get("/{team_member_id}", response_model=TeamMemberResponse)
def get_team_member(team_member_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    member = db.get(TeamMember, team_member_id)
    if member is None:
        raise not_found("Team member")
    return serialize_team_member(member)


@router.put("/{team_member_id}", response_model=TeamMemberResponse)
def update_team_member(
    team_member_id: int,
    payload: TeamMemberUpdate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    member = db.get(TeamMember, team_member_id)
    if member is None:
        raise not_found("Team member")
    try:
        update_member_service(db, member, payload.model_dump(exclude_unset=True))
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc
    db.refresh(member)
    return serialize_team_member(member)


@router.get("/{team_member_id}/products", response_model=TeamMemberProductsResponse)
def get_team_member_product_rows(
    team_member_id: int,
    fiscal_year: int = 2026,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return team_member_products(db, team_member_id, fiscal_year)
    except ValueError as exc:
        raise not_found(str(exc).replace(" not found", "")) from exc
