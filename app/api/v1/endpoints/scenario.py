from fastapi import APIRouter, Depends
from app.core.auth import get_current_user, AuthUser
from app.schemas.scenario import ScenarioCreateRequest
from fastapi import Body

router = APIRouter(tags=["scenario"])


@router.post("/")
async def create_scenario(
    user: AuthUser = Depends(get_current_user),
    scenario_create_request: ScenarioCreateRequest = Body(...),
):
    return scenario_create_request.model_dump()