# app/api/v1/endpoints/tts.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.services.tts_service import TTSService
from app.repositories.voice_line_repository import VoiceLineRepository
from app.core.utils.enums import VoiceLineAudioStatusEnum, ElevenLabsModelEnum
from app.core.config import settings
from app.core.utils.voices_catalog import get_voices_catalog, PREVIEW_VERSION
from app.schemas.tts import SingleTTSRequest, RegenerateTTSRequest, TTSResult, VoiceListResponse, ScenarioTTSRequest, TTSResponse, PublicTTSTestRequest, PublicTTSTestResponse
from sqlalchemy import select
from app.models.voice_line_audio import VoiceLineAudio
from app.core.logging import console_logger
from app.services.voice_line_service import VoiceLineService
from app.celery.tasks.tts import generate_voice_line_task
import asyncio
from datetime import datetime, timezone
import re
from app.core.utils.audio import pcm16_to_wav_with_tempo

router = APIRouter(tags=["tts"])


# Endpoints
@router.get("/voices", response_model=VoiceListResponse)
async def get_available_voices():
    """Get flat list of curated voices with enums for language and gender"""
    base_public = f"{settings.SUPABASE_URL}/storage/v1/object/public/voice-lines/public/voice-previews/{PREVIEW_VERSION}"
    avatar_base_public = f"{settings.SUPABASE_URL}/storage/v1/object/public/avatars/ai/"
    catalog = get_voices_catalog()
    voices = []
    for v in catalog:
        voices.append({
            "id": v["id"],
            "name": v.get("name"),
            "description": v.get("description"),
            "languages": v.get("languages", []),
            "gender": v.get("gender"),
            "avatar_url": f"{avatar_base_public}/{v.get('avatar_url')}" if v.get("avatar_url") else None,
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

        # Schedule Celery job for newly created PENDING
        payload = prepared["background_payload"]
        job_payload = {
            **payload,
            "model": payload["model"].value,  # enum -> string for Celery JSON payload
        }
        generate_voice_line_task.delay(job_payload)
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


@router.post("/generate/public-test", response_model=PublicTTSTestResponse)
async def generate_public_test_audio(
    request: PublicTTSTestRequest,
    tempo: float = 1.1,  
    user: AuthUser = Depends(get_current_user),
):
    try:
        if tempo <= 0.0 or tempo < 0.5 or tempo > 2.0:
            raise HTTPException(status_code=400, detail="tempo must be between 0.5 and 2.0")

        tts = TTSService()
        # Generate PCM audio
        pcm = await tts.generate_audio(
            text=request.text,
            voice_id=request.voice_id,
            model=request.model,
            voice_settings=request.voice_settings,
        )
        # Convert to WAV (16k mono) and apply optional tempo adjustment via shared utility
        wav_bytes = pcm16_to_wav_with_tempo(pcm, tempo=tempo)

        # Build storage path
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        storage_path = f"public/testing/{ts}.wav"

        # Upload to Supabase public path
        def _upload_sync():
            return tts.storage_client.storage.from_(tts.bucket_name).upload(
                path=storage_path,
                file=wav_bytes,
                file_options={
                    "content-type": "audio/wav",
                    "cache-control": "3600",
                    "upsert": "false",
                },
            )

        # Retry on transient network/server errors
        max_attempts = 6
        base_delay = 0.5
        for attempt in range(1, max_attempts + 1):
            try:
                _ = await asyncio.to_thread(_upload_sync)
                break
            except Exception as e:
                msg = str(e).lower()
                transient_tokens = [
                    "timeout",
                    "timed out",
                    "read operation timed out",
                    "connection reset",
                    "econnreset",
                    "upstream connect error",
                    "bad gateway",
                    "service unavailable",
                    "gateway timeout",
                    "temporarily unavailable",
                    "connect error",
                ]
                is_5xx = bool(re.search(r"\b5\d{2}\b", msg)) or any(code in msg for code in [" 502", " 503", " 504"])
                is_transient = is_5xx or any(t in msg for t in transient_tokens)
                if is_transient and attempt < max_attempts:
                    delay = min(10.0, base_delay * (2 ** (attempt - 1)))
                    console_logger.warning(
                        f"Public TTS upload transient failure (attempt {attempt}/{max_attempts}); retrying in {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

        public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{tts.bucket_name}/{storage_path}"
        return PublicTTSTestResponse(success=True, storage_path=storage_path, public_url=public_url)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS public upload failed: {str(e)}")

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
            job_payload = {**payload, "model": payload["model"].value}
            generate_voice_line_task.delay(job_payload)

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
        job_payload = {**payload, "model": payload["model"].value}
        generate_voice_line_task.delay(job_payload)
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


@router.post("/generate/public-test-bulk")
async def generate_public_test_audio_bulk(
    request: dict,
    tempo: float = 1.1,
    user: AuthUser = Depends(get_current_user),
):
    try:
        if tempo <= 0.0 or tempo < 0.5 or tempo > 2.0:
            raise HTTPException(status_code=400, detail="tempo must be between 0.5 and 2.0")

        # Extract parameters, converting single values to lists
        texts = request.get("text", [])
        if isinstance(texts, str):
            texts = [texts]
        
        voice_ids = request.get("voice_id", [])
        if isinstance(voice_ids, str):
            voice_ids = [voice_ids]
            
        models = request.get("model", [])
        if isinstance(models, str):
            models = [models]
            
        # Voice settings - each can be a single value or list
        voice_settings = request.get("voice_settings", {})
        stability_values = voice_settings.get("stability", [0.0])
        if not isinstance(stability_values, list):
            stability_values = [stability_values]
            
        similarity_boost_values = voice_settings.get("similarity_boost", [0.85])
        if not isinstance(similarity_boost_values, list):
            similarity_boost_values = [similarity_boost_values]
            
        style_values = voice_settings.get("style", [1.6])
        if not isinstance(style_values, list):
            style_values = [style_values]
            
        speed_values = voice_settings.get("speed", [1.2])
        if not isinstance(speed_values, list):
            speed_values = [speed_values]
            
        use_speaker_boost_values = voice_settings.get("use_speaker_boost", [False])
        if not isinstance(use_speaker_boost_values, list):
            use_speaker_boost_values = [use_speaker_boost_values]

        tts = TTSService()
        results = []
        
        # Generate all combinations
        import itertools
        combinations = list(itertools.product(
            texts, voice_ids, models, 
            stability_values, similarity_boost_values, style_values, speed_values, use_speaker_boost_values
        ))
        
        for i, (text, voice_id, model_str, stability, similarity_boost, style, speed, use_speaker_boost) in enumerate(combinations):
            try:
                # Convert model string to enum
                if isinstance(model_str, str):
                    try:
                        model_enum = ElevenLabsModelEnum(model_str)
                    except ValueError:
                        model_enum = ElevenLabsModelEnum.ELEVEN_TTV_V3  # fallback
                else:
                    model_enum = model_str  # already an enum
                
                # Create voice settings for this combination
                current_voice_settings = {
                    "stability": stability,
                    "similarity_boost": similarity_boost,
                    "style": style,
                    "speed": speed,
                    "use_speaker_boost": use_speaker_boost
                }
                
                # Generate PCM audio
                pcm = await tts.generate_audio(
                    text=text,
                    voice_id=voice_id,
                    model=model_enum,
                    voice_settings=current_voice_settings,
                )
                
                # Convert to WAV with tempo adjustment
                wav_bytes = pcm16_to_wav_with_tempo(pcm, tempo=tempo)

                # Build storage path with combination info
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                storage_path = f"public/testing/bulk_{ts}_{i:03d}.wav"

                # Upload to Supabase
                def _upload_sync():
                    return tts.storage_client.storage.from_(tts.bucket_name).upload(
                        path=storage_path,
                        file=wav_bytes,
                        file_options={
                            "content-type": "audio/wav",
                            "cache-control": "3600",
                            "upsert": "false",
                        },
                    )

                # Retry logic for upload
                max_attempts = 3
                base_delay = 0.5
                for attempt in range(1, max_attempts + 1):
                    try:
                        _ = await asyncio.to_thread(_upload_sync)
                        break
                    except Exception as e:
                        if attempt < max_attempts:
                            delay = base_delay * (2 ** (attempt - 1))
                            await asyncio.sleep(delay)
                            continue
                        raise

                public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{tts.bucket_name}/{storage_path}"
                
                results.append({
                    "index": i,
                    "public_url": public_url,
                    "storage_path": storage_path,
                    "parameters": {
                        "text": text[:50] + "..." if len(text) > 50 else text,
                        "voice_id": voice_id,
                        "model": model_enum.value,
                        "voice_settings": current_voice_settings,
                        "tempo": tempo
                    }
                })
                
            except Exception as e:
                results.append({
                    "index": i,
                    "error": str(e),
                    "parameters": {
                        "text": text[:50] + "..." if len(text) > 50 else text,
                        "voice_id": voice_id,
                        "model": model_str,
                        "voice_settings": {
                            "stability": stability,
                            "similarity_boost": similarity_boost,
                            "style": style,
                            "speed": speed,
                            "use_speaker_boost": use_speaker_boost
                        },
                        "tempo": tempo
                    }
                })

        return {
            "success": True,
            "total_combinations": len(combinations),
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk TTS generation failed: {str(e)}")