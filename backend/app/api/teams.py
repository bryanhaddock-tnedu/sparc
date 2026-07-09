from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.errors import bad_request
from app.db.session import get_db
from app.schemas import RoadmapForecastAllocationBatchUpsert, TeamRoadmapForecastPlanResponse
from app.services.roadmap_forecasting import team_roadmap_forecast_plan, upsert_team_roadmap_forecast_allocations
from app.services.auth import require_admin, require_named_people_access

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/{team_ref}/roadmap-forecast-plan", response_model=TeamRoadmapForecastPlanResponse)
def get_team_roadmap_forecast_plan(
    team_ref: str,
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
    _viewer=Depends(require_named_people_access),
) -> dict[str, object]:
    return team_roadmap_forecast_plan(db, team_ref, fiscal_year)


@router.put("/{team_ref}/roadmap-forecast-plan", response_model=TeamRoadmapForecastPlanResponse)
def upsert_team_roadmap_forecast_plan(
    team_ref: str,
    payload: RoadmapForecastAllocationBatchUpsert,
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, object]:
    try:
        result = upsert_team_roadmap_forecast_allocations(
            db,
            team_ref,
            fiscal_year,
            [entry.model_dump() for entry in payload.entries],
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc
