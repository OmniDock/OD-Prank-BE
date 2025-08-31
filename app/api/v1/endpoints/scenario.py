from fastapi import APIRouter, Depends, HTTPException, Query, Body
from app.core.auth import get_current_user, AuthUser
from app.schemas.scenario import (
    ScenarioCreateRequest, 
    ScenarioCreateResponse, 
    ScenarioResponse, 
    VoiceLineEnhancementRequest, 
    VoiceLineEnhancementResponse
)
from app.services.scenario_service import ScenarioService
from app.core.database import AsyncSession, get_db_session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.core.logging import console_logger
import uuid

router = APIRouter(tags=["scenario"])

# Session store for clarification loops (should be Redis in production)
sessions: Dict[str, Any] = {}


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
        # Import here to avoid circular dependency
        from app.langchain import ScenarioProcessor, ScenarioState
        
        # Validate request
        if not request.scenario and not request.session_id:
            raise HTTPException(
                status_code=400,
                detail="Either 'scenario' or 'session_id' must be provided"
            )
        
        processor = ScenarioProcessor()
        
        # Handle session continuation
        if request.session_id and request.session_id in sessions:
            console_logger.info(f"Continuing session {request.session_id}")
            # Reconstruct state from stored dict
            stored_state = sessions[request.session_id]["state"]
            if isinstance(stored_state, dict):
                state = ScenarioState(**stored_state)
            else:
                state = stored_state
            
            # Add clarifications if provided
            if request.clarifications:
                state.clarifications = request.clarifications
                state.require_clarification = False
        else:
            # Create new session
            if not request.scenario:
                raise HTTPException(
                    status_code=400,
                    detail="Scenario is required for new sessions"
                )
            
            console_logger.info("Creating new session")
            state = ScenarioState(
                scenario_data=request.scenario,
                require_clarification=True
            )
        
        # Process the scenario
        result = await processor.process(state)
        
        # Convert result to state if it's a dict
        if isinstance(result, dict):
            state = ScenarioState(**result)
        else:
            state = result
        
        # Check if clarification is needed
        if state.require_clarification and state.clarifying_questions:
            session_id = str(uuid.uuid4())
            # Store state as dict to avoid serialization issues
            sessions[session_id] = {
                "state": state.model_dump() if hasattr(state, 'model_dump') else state,
                "user_id": user.id
            }
            
            return ScenarioProcessResponse(
                status="needs_clarification",
                session_id=session_id,
                clarifying_questions=state.clarifying_questions
            )
        
        # Processing complete - create scenario
        # Create a fresh service instance to ensure proper async context
        try:
            scenario_service = ScenarioService(db_session)
            scenario_response = await scenario_service.create_scenario_from_state(user, state)
            
            # Clean up session
            if request.session_id in sessions:
                del sessions[request.session_id]
            
            return ScenarioProcessResponse(
                status="complete",
                scenario_id=scenario_response.scenario.id
            )
        except Exception as e:
            console_logger.error(f"Failed to create scenario: {str(e)}")
            # Try to provide more specific error info
            if "greenlet" in str(e).lower():
                raise HTTPException(
                    status_code=500,
                    detail="Database connection error. Please try again."
                )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create scenario: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        console_logger.error(f"Processing failed: {str(e)}")
        return ScenarioProcessResponse(
            status="error",
            error=str(e)
        )


@router.post("/", response_model=ScenarioCreateResponse)
async def create_scenario(
    scenario_create_request: ScenarioCreateRequest = Body(...),
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> ScenarioCreateResponse:
    """
    Create a new scenario (direct, no clarification support)
    
    For backward compatibility - processes immediately without clarification loop
    """
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


class EnhanceScenarioRequest(BaseModel):
    """Request for enhancing an entire scenario"""
    scenario_id: int = Field(description="Scenario ID to enhance")
    user_feedback: str = Field(description="User's improvement feedback")


@router.post("/{scenario_id}/enhance", response_model=ScenarioResponse)
async def enhance_scenario(
    scenario_id: int,
    request: EnhanceScenarioRequest = Body(...),
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> ScenarioResponse:
    """
    Enhance an entire scenario based on user feedback
    
    This creates a new version of all voice lines based on the feedback
    """
    try:
        scenario_service = ScenarioService(db_session)
        enhanced_scenario = await scenario_service.enhance_full_scenario(
            user, scenario_id, request.user_feedback
        )
        return enhanced_scenario
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enhance scenario: {str(e)}")


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
    user: AuthUser = Depends(get_current_user)
) -> Dict[str, str]:
    """Clear a clarification session"""
    if session_id in sessions:
        # Verify ownership
        if sessions[session_id]["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        del sessions[session_id]
        return {"message": f"Session {session_id} cleared"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")