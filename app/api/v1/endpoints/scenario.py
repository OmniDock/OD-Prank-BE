from fastapi import APIRouter, Depends, HTTPException, Query, Body
from app.core.auth import get_current_user, AuthUser
from app.schemas.scenario import (
    ScenarioCreateRequest, 
    ScenarioResponse, 
    VoiceLineEnhancementRequest, 
    VoiceLineEnhancementResponse
)
from app.services.scenario_service import ScenarioService
from app.core.database import AsyncSession, get_db_session
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from app.core.logging import console_logger

router = APIRouter(tags=["scenario"])

# ========= PROCESS SCENARIO WITH CLARIFICATION SUPPORT =========

class ScenarioProcessRequest(BaseModel):
    """Request for processing a scenario with clarification support"""
    scenario: Optional[ScenarioCreateRequest] = Field(
        None, 
        description="Scenario data (required for new sessions)"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for continuing with clarifications"
    )
    clarifications: Optional[List[str]] = Field(
        None,
        description="Answers to clarifying questions"
    )


class ScenarioProcessResponse(BaseModel):
    """Response from scenario processing"""
    status: str = Field(description="Status: needs_clarification, complete, error")
    session_id: Optional[str] = Field(None, description="Session ID for continuation")
    clarifying_questions: Optional[List[str]] = None
    scenario_id: Optional[int] = Field(None, description="Created scenario ID")
    error: Optional[str] = None


@router.post("/process", response_model=ScenarioProcessResponse)
async def process_scenario(
    request: ScenarioProcessRequest = Body(...),
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> ScenarioProcessResponse:
    """
    Process a scenario with clarification support
    
    This endpoint supports a two-step flow:
    1. Initial request with scenario → may return clarifying questions
    2. Follow-up with session_id and clarifications → creates scenario
    """
    try:
        service = ScenarioService(db_session)
        result = await service.process_with_clarification_flow(
            user=user,
            scenario_data=request.scenario,
            session_id=request.session_id,
            clarifications=request.clarifications
        )
        return ScenarioProcessResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        console_logger.error(f"Processing failed: {str(e)}")
        return ScenarioProcessResponse(status="error", error=str(e))
    


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


# ========= RETRIEVE SCENARIOS AND CRUD =========

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
        console_logger.warning(f"Scenario {scenario_id} not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        console_logger.error(f"Error getting scenario {scenario_id}: {e}")
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
        updated = await service.update_preferred_voice(user, scenario_id, payload.preferred_voice_id)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update preferred voice: {str(e)}")


@router.delete("/sessions/{session_id}")
async def clear_session(
    session_id: str,
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
) -> Dict[str, str]:
    """Clear a clarification session"""
    service = ScenarioService(db_session)
    service.clear_clarification_session(session_id, user)
    return {"message": f"Session {session_id} cleared"}