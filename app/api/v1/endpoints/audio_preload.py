# OD-Prank-BE/app/api/v1/endpoints/audio_preload.py
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.services.audio_preload_service import AudioPreloadService
from app.core.utils.enums import VoiceLineTypeEnum
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

router = APIRouter(tags=["audio-preload"])


class PreloadResponse(BaseModel):
    success: bool
    message: str
    stats: Dict[str, Any]


class PreloadStatsResponse(BaseModel):
    stats: Dict[str, Any]


class DropResponse(BaseModel):
    success: bool
    message: str


@router.post("/scenarios/{scenario_id}/preload", response_model=PreloadResponse)
async def preload_scenario_audio(
    scenario_id: int,
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
    preferred_voice_id: Optional[str] = Query(None, description="Optional voice ID filter")
) -> PreloadResponse:
    """
    Preload all available audio files for a scenario into memory for quick access
    """
    try:
        service = AudioPreloadService(db_session)
        success, message, stats = await service.preload_scenario_audio(
            user.id, scenario_id, preferred_voice_id
        )
        
        return PreloadResponse(
            success=success,
            message=message,
            stats=stats
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to preload audio: {str(e)}")


@router.delete("/scenarios/{scenario_id}/preload", response_model=DropResponse)
async def drop_scenario_audio(
    scenario_id: int,
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> DropResponse:
    """
    Remove preloaded audio for a scenario from memory
    """
    try:
        service = AudioPreloadService(db_session)
        success = service.drop_preloaded_audio(user.id, scenario_id)
        
        if success:
            return DropResponse(
                success=True,
                message=f"Successfully dropped preloaded audio for scenario {scenario_id}"
            )
        else:
            return DropResponse(
                success=False,
                message=f"No preloaded audio found for scenario {scenario_id}"
            )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to drop preloaded audio: {str(e)}")


@router.get("/scenarios/{scenario_id}/preload/stats", response_model=PreloadStatsResponse)
async def get_scenario_preload_stats(
    scenario_id: int,
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> PreloadStatsResponse:
    """
    Get statistics about preloaded audio for a scenario
    """
    try:
        service = AudioPreloadService(db_session)
        stats = service.get_preload_stats(user.id, scenario_id)
        
        return PreloadStatsResponse(stats=stats)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get preload stats: {str(e)}")


@router.get("/preload/stats", response_model=PreloadStatsResponse)
async def get_global_preload_stats(
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> PreloadStatsResponse:
    """
    Get global statistics about all preloaded audio
    """
    try:
        service = AudioPreloadService(db_session)
        stats = service.get_preload_stats()
        
        return PreloadStatsResponse(stats=stats)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get global preload stats: {str(e)}")


@router.delete("/preload/all", response_model=DropResponse)
async def drop_all_preloaded_audio(
    user: AuthUser = Depends(get_current_user),
) -> DropResponse:
    """
    Clear all preloaded audio from memory (admin function)
    """
    try:
        dropped_count = AudioPreloadService.drop_all_preloaded_audio()
        
        return DropResponse(
            success=True,
            message=f"Successfully dropped all preloaded audio ({dropped_count} scenarios)"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to drop all preloaded audio: {str(e)}")