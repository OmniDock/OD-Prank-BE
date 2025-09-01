# app/api/v1/endpoints/tts.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.services.tts_service import TTSService
from app.repositories.voice_line_repository import VoiceLineRepository
from app.core.utils.enums import VoiceLineAudioStatusEnum
from app.core.config import settings
from app.core.utils.voices_catalog import get_voices_catalog, PREVIEW_VERSION
from app.schemas.tts import SingleTTSRequest, RegenerateTTSRequest, TTSResult, VoiceListResponse, ScenarioTTSRequest, TTSResponse
from sqlalchemy import select
from app.models.voice_line_audio import VoiceLineAudio
from app.core.logging import console_logger
from app.services.voice_line_service import VoiceLineService, background_generate_and_store_audio

router = APIRouter(tags=["tts"])


# Endpoints
@router.get("/voices", response_model=VoiceListResponse)
async def get_available_voices():
    """Get flat list of curated voices with enums for language and gender"""
    base_public = f"{settings.SUPABASE_URL}/storage/v1/object/public/voice-lines/public/voice-previews/{PREVIEW_VERSION}"
    catalog = get_voices_catalog()
    voices = []
    for v in catalog:
        voices.append({
            "id": v["id"],
            "name": v.get("name"),
            "description": v.get("description"),
            "languages": v.get("languages", []),
            "gender": v.get("gender"),
            "preview_url": f"{base_public}/{v['id']}.wav",
        })

    return VoiceListResponse(voices=voices)

@router.post("/generate/single", response_model=TTSResult)
async def generate_single_voice_line(
    request: SingleTTSRequest,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Generate TTS audio for a single voice line"""
    try:
        if not request.voice_id:
            raise HTTPException(status_code=400, detail="voice_id is required")

        svc = VoiceLineService(db_session)
        prepared = await svc.request_tts_single(user, request.voice_line_id, request.voice_id)

        if prepared["status"] == "ready":
            return TTSResult(
                voice_line_id=request.voice_line_id,
                success=True,
                signed_url=prepared["signed_url"],
                storage_path=prepared["storage_path"],
                error_message=None,
            )
        if prepared["status"] == "in_progress":
            return TTSResult(
                voice_line_id=request.voice_line_id,
                success=False,
                signed_url=None,
                storage_path=None,
                error_message="Audio generation already in progress",
            )

        # Schedule background job for newly created PENDING
        payload = prepared["background_payload"]
        background_tasks.add_task(background_generate_and_store_audio, **payload)
        return TTSResult(
            voice_line_id=request.voice_line_id,
            success=True,
            signed_url=None,
            storage_path=None,
            error_message="Audio generation started in background",
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")

@router.post("/generate/scenario", response_model=TTSResponse)
async def generate_scenario_voice_lines(
    request: ScenarioTTSRequest,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Generate TTS audio for all voice lines in a scenario"""
    try:
        svc = VoiceLineService(db_session)
        results, payloads = await svc.request_tts_for_scenario(user, request.scenario_id, request.voice_id)
        for payload in payloads:
            background_tasks.add_task(background_generate_and_store_audio, **payload)

        successful_count = sum(1 for r in results if r.get("success"))
        failed_count = len(results) - successful_count
        return TTSResponse(
            success=successful_count > 0,
            total_processed=len(results),
            successful_count=successful_count,
            failed_count=failed_count,
            results=[
                TTSResult(
                    voice_line_id=r["voice_line_id"],
                    success=r.get("success", False),
                    signed_url=r.get("signed_url"),
                    storage_path=r.get("storage_path"),
                    error_message=r.get("error_message"),
                ) for r in results
            ]
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scenario TTS generation failed: {str(e)}")

@router.post("/regenerate", response_model=TTSResult)
async def regenerate_voice_line_audio(
    request: RegenerateTTSRequest,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Regenerate TTS audio for a voice line (replaces existing audio)"""
    try:
        if not request.voice_id:
            raise HTTPException(status_code=400, detail="voice_id is required")

        svc = VoiceLineService(db_session)
        prepared = await svc.request_tts_regenerate(user, request.voice_line_id, request.voice_id)

        if prepared["status"] == "ready":
            return TTSResult(
                voice_line_id=request.voice_line_id,
                success=True,
                signed_url=prepared["signed_url"],
                storage_path=prepared["storage_path"],
                error_message=None,
            )
        if prepared["status"] == "in_progress":
            return TTSResult(
                voice_line_id=request.voice_line_id,
                success=False,
                signed_url=None,
                storage_path=None,
                error_message="Audio generation already in progress",
            )

        payload = prepared["background_payload"]
        background_tasks.add_task(background_generate_and_store_audio, **payload)
        return TTSResult(
            voice_line_id=request.voice_line_id,
            success=True,
            signed_url=None,
            storage_path=None,
            error_message="Audio generation started in background",
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS regeneration failed: {str(e)}")

@router.get("/audio-url/{voice_line_id}")
async def get_voice_line_audio_url(
    voice_line_id: int,
    expires_in: int = 3600 * 12,  # 12 hours default
    voice_id: str | None = None,
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Get a fresh signed URL for accessing voice line audio"""
    try:
        svc = VoiceLineService(db_session)
        result = await svc.get_audio_url_for_voice_line(user, voice_line_id, expires_in, voice_id)
        if result["status"] == "PENDING":
            return JSONResponse(status_code=202, content={"status": "PENDING"})
        return {"signed_url": result["signed_url"], "expires_in": result["expires_in"]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audio URL: {str(e)}")
