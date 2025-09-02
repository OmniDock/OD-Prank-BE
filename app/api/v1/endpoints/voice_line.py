from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.services.voice_line_service import VoiceLineService
from app.core.logging import console_logger

router = APIRouter(tags=["voice-lines"])


@router.get("/summary")
async def get_voice_lines_summary(
    scenario_id: int,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        service = VoiceLineService(db_session)
        payload, etag = await service.build_audio_summary(user, scenario_id)
        if_none_match = request.headers.get("if-none-match") or request.headers.get("If-None-Match")
        if if_none_match and if_none_match == etag:
            return Response(status_code=304, headers={"ETag": etag})
        return JSONResponse(content=payload, headers={"ETag": etag})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        console_logger.error(f"Voice lines summary failed for scenario {scenario_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load voice lines summary")
