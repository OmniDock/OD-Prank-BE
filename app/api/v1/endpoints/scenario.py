from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.auth import get_current_user, AuthUser
from app.schemas.scenario import ScenarioCreateRequest, ScenarioCreateResponse, ScenarioResponse, VoiceLineEnhancementRequest, VoiceLineEnhancementResponse
from fastapi import Body
from app.services.scenario_service import ScenarioService
from app.core.database import AsyncSession, get_db_session
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(tags=["scenario"])


@router.post("/", response_model=ScenarioCreateResponse)
async def create_scenario(
    scenario_create_request: ScenarioCreateRequest = Body(...),
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> ScenarioCreateResponse:
    """Create a new scenario with LangChain processing and save to database"""
    try:
        scenario_service = ScenarioService(db_session)
        result = await scenario_service.create_scenario(user, scenario_create_request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create scenario: {str(e)}")


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: int,
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> ScenarioResponse:
    """Get a scenario by ID"""
    try:
        scenario_service = ScenarioService(db_session)
        return await scenario_service.get_scenario(user, scenario_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scenario: {str(e)}")


@router.get("/", response_model=List[ScenarioResponse])
async def get_user_scenarios(
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
    limit: int = Query(50, ge=1, le=100, description="Number of scenarios to return"),
    offset: int = Query(0, ge=0, description="Number of scenarios to skip"),
) -> List[ScenarioResponse]:
    """Get scenarios for the current user"""
    try:
        scenario_service = ScenarioService(db_session)
        return await scenario_service.get_user_scenarios(user, limit, offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scenarios: {str(e)}")
    



@router.post("/voice-lines/enhance", response_model=VoiceLineEnhancementResponse)
async def enhance_voice_lines(
    request: VoiceLineEnhancementRequest = Body(...),
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> VoiceLineEnhancementResponse:
    """Enhance multiple voice lines with user feedback"""
    try:
        scenario_service = ScenarioService(db_session)
        result = await scenario_service.enhance_voice_lines_with_feedback(
            user, request.voice_line_ids, request.user_feedback
        )
        return VoiceLineEnhancementResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enhance voice lines: {str(e)}")


class ScenarioUpdatePreferredVoice(BaseModel):
    preferred_voice_id: str


@router.patch("/{scenario_id}/preferred-voice", response_model=ScenarioResponse)
async def update_scenario_preferred_voice(
    scenario_id: int,
    payload: ScenarioUpdatePreferredVoice = Body(...),
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Set or change the scenario's preferred voice id"""
    try:
        service = ScenarioService(db_session)
        updated = await service.set_preferred_voice(user, scenario_id, payload.preferred_voice_id)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update preferred voice: {str(e)}")