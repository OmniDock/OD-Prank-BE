# app/api/v1/endpoints/tts.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.services.tts_service import TTSService
from app.repositories.scenario_repository import ScenarioRepository
from app.core.utils.enums import VoiceLineAudioStatusEnum, ElevenLabsModelEnum
from app.core.config import settings
from app.core.utils.voices_catalog import get_voices_catalog, PREVIEW_VERSION
from app.schemas.tts import SingleTTSRequest, BatchTTSRequest, ScenarioTTSRequest, RegenerateTTSRequest, TTSResult, TTSResponse, VoiceListResponse
from sqlalchemy import select
from app.models.voice_line_audio import VoiceLineAudio
from app.core.logging import console_logger

router = APIRouter(tags=["tts"])


# Background task functions
async def background_generate_and_store_audio(
    voice_line_id: int,
    user_id: str,
    text: str,
    voice_id: str,
    model: ElevenLabsModelEnum,
    voice_settings: dict,
    content_hash: str
):
    """Background task to generate and store TTS audio"""
    try:
        from app.core.database import get_db_session
        from app.models.voice_line_audio import VoiceLineAudio
        from app.core.utils.enums import VoiceLineAudioStatusEnum
        
        console_logger = __import__('app.core.logging', fromlist=['console_logger']).console_logger
        console_logger.info(f"Background TTS generation started for voice line {voice_line_id}")
        
        # Create new database session for background task
        async for db_session in get_db_session():
            try:
                tts_service = TTSService()
                
                # Generate and store audio
                success, signed_url, storage_path, error_msg = await tts_service.generate_and_store_audio(
                    text=text,
                    voice_line_id=voice_line_id,
                    user_id=user_id,
                    voice_id=voice_id,
                    model=model,
                    voice_settings=voice_settings,
                )
                
                if success and storage_path:
                    # Create and persist the audio record
                    asset = VoiceLineAudio(
                        voice_line_id=voice_line_id,
                        voice_id=voice_id,
                        model_id=model,
                        voice_settings=voice_settings,
                        storage_path=storage_path,
                        duration_ms=None,
                        size_bytes=None,
                        text_hash=tts_service.compute_text_hash(text),
                        settings_hash=tts_service.compute_settings_hash(voice_id, model, voice_settings),
                        content_hash=content_hash,
                        status=VoiceLineAudioStatusEnum.READY,
                    )
                    
                    db_session.add(asset)
                    await db_session.commit()
                    console_logger.info(f"Background TTS generation completed successfully for voice line {voice_line_id}")
                else:
                    console_logger.error(f"Background TTS generation failed for voice line {voice_line_id}: {error_msg}")
                    
            except Exception as e:
                console_logger.error(f"Background TTS generation error for voice line {voice_line_id}: {str(e)}")
                await db_session.rollback()
            finally:
                await db_session.close()
                break
                
    except Exception as e:
        console_logger.error(f"Background TTS task setup failed for voice line {voice_line_id}: {str(e)}")


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
        # Verify user owns the voice line
        repository = ScenarioRepository(db_session)
        voice_line = await repository.get_voice_line_by_id_with_user_check(request.voice_line_id, user.id)
        
        if not voice_line:
            raise HTTPException(status_code=404, detail="Voice line not found or access denied")
        
        # Prepare hashing & reuse
        tts_service = TTSService()
        if not request.voice_id:
            raise HTTPException(status_code=400, detail="voice_id is required")
        
        selected_voice_id = request.voice_id
        voice_settings = tts_service.default_voice_settings()
        forced_model = ElevenLabsModelEnum.ELEVEN_TTV_V3
        content_hash = tts_service.compute_content_hash(voice_line.text, selected_voice_id, forced_model, voice_settings)

        # Try reuse existing READY asset
        result = await db_session.execute(
            select(VoiceLineAudio).where(
                VoiceLineAudio.voice_line_id == request.voice_line_id,
                VoiceLineAudio.content_hash == content_hash,
                VoiceLineAudio.status == VoiceLineAudioStatusEnum.READY,
            ).limit(1)
        )


        existing: VoiceLineAudio | None = result.scalar_one_or_none()

        if existing and existing.storage_path:
            signed_url = await tts_service.get_audio_url(existing.storage_path)
            return TTSResult(
                voice_line_id=request.voice_line_id,
                success=True,
                signed_url=signed_url,
                storage_path=existing.storage_path,
                error_message=None,
            )

        # Check if generation is already in progress
        in_progress_result = await db_session.execute(
            select(VoiceLineAudio).where(
                VoiceLineAudio.voice_line_id == request.voice_line_id,
                VoiceLineAudio.content_hash == content_hash,
                VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
            ).limit(1)
        )
        in_progress: VoiceLineAudio | None = in_progress_result.scalar_one_or_none()

        if in_progress:
            return TTSResult(
                voice_line_id=request.voice_line_id,
                success=False,
                signed_url=None,
                storage_path=None,
                error_message="Audio generation already in progress",
            )

        # Create processing record to prevent duplicate requests
        processing_asset = VoiceLineAudio(
            voice_line_id=request.voice_line_id,
            voice_id=selected_voice_id,
            model_id=forced_model,
            voice_settings=voice_settings,
            storage_path=None,  # Will be set when completed
            duration_ms=None,
            size_bytes=None,
            text_hash=tts_service.compute_text_hash(voice_line.text),
            settings_hash=tts_service.compute_settings_hash(selected_voice_id, forced_model, voice_settings),
            content_hash=content_hash,
            status=VoiceLineAudioStatusEnum.PENDING,
            error=None,
        )
        
        db_session.add(processing_asset)
        await db_session.commit()

        # Start background generation
        background_tasks.add_task(
            background_generate_and_store_audio,
            voice_line_id=request.voice_line_id,
            user_id=str(user.id),
            text=voice_line.text,
            voice_id=selected_voice_id,
            model=forced_model,
            voice_settings=voice_settings,
            content_hash=content_hash,
        )

        return TTSResult(
            voice_line_id=request.voice_line_id,
            success=True,
            signed_url=None,  # Will be available once background task completes
            storage_path=None,
            error_message="Audio generation started in background",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")

@router.post("/generate/batch", response_model=TTSResponse)
async def generate_batch_voice_lines(
    request: BatchTTSRequest,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Generate TTS audio for multiple voice lines"""
    try:
        repository = ScenarioRepository(db_session)
        tts_service = TTSService()
        
        # Verify user owns all voice lines
        voice_lines = await repository.get_voice_lines_by_ids_with_user_check(
            request.voice_line_ids, user.id
        )
        
        if len(voice_lines) != len(request.voice_line_ids):
            found_ids = [vl.id for vl in voice_lines]
            missing_ids = [vid for vid in request.voice_line_ids if vid not in found_ids]
            raise HTTPException(
                status_code=404, 
                detail=f"Voice lines not found or access denied: {missing_ids}"
            )
        
        results = []
        
        # Require voice_id for batch generation
        if not request.voice_id:
            raise HTTPException(status_code=400, detail="voice_id is required")

        # Process each voice line
        for voice_line in voice_lines:
            try:
                selected_voice_id = request.voice_id
                voice_settings = tts_service.default_voice_settings()
                forced_model = ElevenLabsModelEnum.ELEVEN_TTV_V3
                content_hash = tts_service.compute_content_hash(voice_line.text, selected_voice_id, forced_model, voice_settings)

                # Reuse check
                r = await db_session.execute(
                    select(VoiceLineAudio).where(
                        VoiceLineAudio.voice_line_id == voice_line.id,
                        VoiceLineAudio.content_hash == content_hash,
                        VoiceLineAudio.status == VoiceLineAudioStatusEnum.READY,
                    ).limit(1)
                )
                existing: VoiceLineAudio | None = r.scalar_one_or_none()

                if existing and existing.storage_path:
                    signed_url = await tts_service.get_audio_url(existing.storage_path)
                    results.append(TTSResult(
                        voice_line_id=voice_line.id,
                        success=True,
                        signed_url=signed_url,
                        storage_path=existing.storage_path,
                        error_message=None,
                    ))
                    continue

                # If a matching PENDING exists, avoid duplicate
                in_progress_result = await db_session.execute(
                    select(VoiceLineAudio).where(
                        VoiceLineAudio.voice_line_id == voice_line.id,
                        VoiceLineAudio.content_hash == content_hash,
                        VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
                    ).limit(1)
                )
                in_progress: VoiceLineAudio | None = in_progress_result.scalar_one_or_none()
                if in_progress:
                    results.append(TTSResult(
                        voice_line_id=voice_line.id,
                        success=False,
                        signed_url=None,
                        storage_path=None,
                        error_message="Audio generation already in progress",
                    ))
                    continue

                # Create PENDING record
                processing_asset = VoiceLineAudio(
                    voice_line_id=voice_line.id,
                    voice_id=selected_voice_id,
                    model_id=forced_model,
                    voice_settings=voice_settings,
                    storage_path=None,
                    duration_ms=None,
                    size_bytes=None,
                    text_hash=tts_service.compute_text_hash(voice_line.text),
                    settings_hash=tts_service.compute_settings_hash(selected_voice_id, forced_model, voice_settings),
                    content_hash=content_hash,
                    status=VoiceLineAudioStatusEnum.PENDING,
                    error=None,
                )
                db_session.add(processing_asset)
                await db_session.commit()

                # Start background generation
                background_tasks.add_task(
                    background_generate_and_store_audio,
                    voice_line_id=voice_line.id,
                    user_id=str(user.id),
                    text=voice_line.text,
                    voice_id=selected_voice_id,
                    model=forced_model,
                    voice_settings=voice_settings,
                    content_hash=content_hash,
                )

                results.append(TTSResult(
                    voice_line_id=voice_line.id,
                    success=True,
                    signed_url=None,
                    storage_path=None,
                    error_message="Audio generation started in background",
                ))
                
            except Exception as e:
                results.append(TTSResult(
                    voice_line_id=voice_line.id,
                    success=False,
                    error_message=f"Generation failed: {str(e)}"
                ))
        
        # Nothing else to commit here (each PENDING insert committed immediately)
        
        successful_count = sum(1 for r in results if r.success)
        
        return TTSResponse(
            success=successful_count > 0,
            total_processed=len(results),
            successful_count=successful_count,
            failed_count=len(results) - successful_count,
            results=results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await repository.rollback()
        raise HTTPException(status_code=500, detail=f"Batch TTS generation failed: {str(e)}")

@router.post("/generate/scenario", response_model=TTSResponse)
async def generate_scenario_voice_lines(
    request: ScenarioTTSRequest,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Generate TTS audio for all voice lines in a scenario"""
    try:
        repository = ScenarioRepository(db_session)
        
        # Verify user owns the scenario
        scenario = await repository.get_scenario_by_id(request.scenario_id, user.id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found or access denied")
        
        # Get all voice lines for the scenario
        voice_lines = await repository.get_voice_lines_by_scenario_id(request.scenario_id)
        
        if not voice_lines:
            raise HTTPException(status_code=404, detail="No voice lines found for this scenario")
        
        tts_service = TTSService()
        results = []
        
        # Determine voice to use: request.voice_id or scenario preferred
        selected_default_voice_id = request.voice_id or scenario.preferred_voice_id
        if not selected_default_voice_id:
            raise HTTPException(status_code=400, detail="voice_id is required (or set preferred voice on scenario)")
        
        # Process each voice line
        for voice_line in voice_lines:
            try:
                selected_voice_id = selected_default_voice_id
                voice_settings = tts_service.default_voice_settings()
                forced_model = ElevenLabsModelEnum.ELEVEN_TTV_V3
                content_hash = tts_service.compute_content_hash(voice_line.text, selected_voice_id, forced_model, voice_settings)

                # Reuse check
                r = await db_session.execute(
                    select(VoiceLineAudio).where(
                        VoiceLineAudio.voice_line_id == voice_line.id,
                        VoiceLineAudio.content_hash == content_hash,
                        VoiceLineAudio.status == VoiceLineAudioStatusEnum.READY,
                    ).limit(1)
                )
                existing: VoiceLineAudio | None = r.scalar_one_or_none()

                if existing and existing.storage_path:
                    signed_url = await tts_service.get_audio_url(existing.storage_path)
                    results.append(TTSResult(
                        voice_line_id=voice_line.id,
                        success=True,
                        signed_url=signed_url,
                        storage_path=existing.storage_path,
                        error_message=None,
                    ))
                    continue

                # If a matching PENDING exists, avoid duplicate
                in_progress_result = await db_session.execute(
                    select(VoiceLineAudio).where(
                        VoiceLineAudio.voice_line_id == voice_line.id,
                        VoiceLineAudio.content_hash == content_hash,
                        VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
                    ).limit(1)
                )
                in_progress: VoiceLineAudio | None = in_progress_result.scalar_one_or_none()
                if in_progress:
                    results.append(TTSResult(
                        voice_line_id=voice_line.id,
                        success=False,
                        signed_url=None,
                        storage_path=None,
                        error_message="Audio generation already in progress",
                    ))
                    continue

                # Create PENDING record
                processing_asset = VoiceLineAudio(
                    voice_line_id=voice_line.id,
                    voice_id=selected_voice_id,
                    model_id=forced_model,
                    voice_settings=voice_settings,
                    storage_path=None,
                    duration_ms=None,
                    size_bytes=None,
                    text_hash=tts_service.compute_text_hash(voice_line.text),
                    settings_hash=tts_service.compute_settings_hash(selected_voice_id, forced_model, voice_settings),
                    content_hash=content_hash,
                    status=VoiceLineAudioStatusEnum.PENDING,
                    error=None,
                )
                db_session.add(processing_asset)
                await db_session.commit()

                # Start background generation
                background_tasks.add_task(
                    background_generate_and_store_audio,
                    voice_line_id=voice_line.id,
                    user_id=str(user.id),
                    text=voice_line.text,
                    voice_id=selected_voice_id,
                    model=forced_model,
                    voice_settings=voice_settings,
                    content_hash=content_hash,
                )

                results.append(TTSResult(
                    voice_line_id=voice_line.id,
                    success=True,
                    signed_url=None,
                    storage_path=None,
                    error_message="Audio generation started in background",
                ))
                
            except Exception as e:
                results.append(TTSResult(
                    voice_line_id=voice_line.id,
                    success=False,
                    error_message=f"Generation failed: {str(e)}"
                ))
        
        # Nothing else to commit here (each PENDING insert committed immediately)
        
        successful_count = sum(1 for r in results if r.success)
        
        return TTSResponse(
            success=successful_count > 0,
            total_processed=len(results),
            successful_count=successful_count,
            failed_count=len(results) - successful_count,
            results=results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await repository.rollback()
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
        repository = ScenarioRepository(db_session)
        
        # Verify user owns the voice line and get current storage info
        voice_line = await repository.get_voice_line_by_id_with_user_check(request.voice_line_id, user.id)
        
        if not voice_line:
            raise HTTPException(status_code=404, detail="Voice line not found or access denied")
        
        # Generate (with reuse); keep history (no delete)
        tts_service = TTSService()
        if not request.voice_id:
            raise HTTPException(status_code=400, detail="voice_id is required")
        selected_voice_id = request.voice_id
        voice_settings = tts_service.default_voice_settings()
        forced_model = ElevenLabsModelEnum.ELEVEN_TTV_V3
        content_hash = tts_service.compute_content_hash(voice_line.text, selected_voice_id, forced_model, voice_settings)

        # Reuse if available
        r = await db_session.execute(
            select(VoiceLineAudio).where(
                VoiceLineAudio.voice_line_id == request.voice_line_id,
                VoiceLineAudio.content_hash == content_hash,
                VoiceLineAudio.status == VoiceLineAudioStatusEnum.READY,
            ).limit(1)
        )
        existing: VoiceLineAudio | None = r.scalar_one_or_none()

        if existing and existing.storage_path:
            signed_url = await tts_service.get_audio_url(existing.storage_path)
            return TTSResult(
                voice_line_id=request.voice_line_id,
                success=True,
                signed_url=signed_url,
                storage_path=existing.storage_path,
                error_message=None,
            )

        # If a matching PENDING exists, avoid duplicate
        in_progress_result = await db_session.execute(
            select(VoiceLineAudio).where(
                VoiceLineAudio.voice_line_id == request.voice_line_id,
                VoiceLineAudio.content_hash == content_hash,
                VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
            ).limit(1)
        )
        in_progress: VoiceLineAudio | None = in_progress_result.scalar_one_or_none()
        if in_progress:
            return TTSResult(
                voice_line_id=request.voice_line_id,
                success=False,
                signed_url=None,
                storage_path=None,
                error_message="Audio generation already in progress",
            )

        # Create PENDING record and start background generation
        processing_asset = VoiceLineAudio(
            voice_line_id=request.voice_line_id,
            voice_id=selected_voice_id,
            model_id=forced_model,
            voice_settings=voice_settings,
            storage_path=None,
            duration_ms=None,
            size_bytes=None,
            text_hash=tts_service.compute_text_hash(voice_line.text),
            settings_hash=tts_service.compute_settings_hash(selected_voice_id, forced_model, voice_settings),
            content_hash=content_hash,
            status=VoiceLineAudioStatusEnum.PENDING,
            error=None,
        )
        db_session.add(processing_asset)
        await db_session.commit()

        background_tasks.add_task(
            background_generate_and_store_audio,
            voice_line_id=request.voice_line_id,
            user_id=str(user.id),
            text=voice_line.text,
            voice_id=selected_voice_id,
            model=forced_model,
            voice_settings=voice_settings,
            content_hash=content_hash,
        )

        return TTSResult(
            voice_line_id=request.voice_line_id,
            success=True,
            signed_url=None,
            storage_path=None,
            error_message="Audio generation started in background",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await repository.rollback()
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

        repository = ScenarioRepository(db_session)
        voice_line = await repository.get_voice_line_by_id_with_user_check(voice_line_id, user.id)
        
        if not voice_line:
            raise HTTPException(status_code=404, detail="Voice line not found or access denied")
        
        tts_service = TTSService()

        if voice_id:
            # Find latest READY asset for this voice and current text (match by text_hash)
            text_hash = tts_service.compute_text_hash(voice_line.text)
            r = await db_session.execute(
                select(VoiceLineAudio).where(
                    VoiceLineAudio.voice_line_id == voice_line_id,
                    VoiceLineAudio.voice_id == voice_id,
                    VoiceLineAudio.text_hash == text_hash,
                    VoiceLineAudio.status == VoiceLineAudioStatusEnum.READY,
                ).order_by(VoiceLineAudio.created_at.desc()).limit(1)
            )
        else:
            # Fallback: latest READY asset regardless of voice
            r = await db_session.execute(
                select(VoiceLineAudio).where(
                    VoiceLineAudio.voice_line_id == voice_line_id,
                    VoiceLineAudio.status == VoiceLineAudioStatusEnum.READY,
                ).order_by(VoiceLineAudio.created_at.desc()).limit(1)
            )

        asset: VoiceLineAudio | None = r.scalar_one_or_none()
        if not asset or not asset.storage_path:
            # If no READY asset, check if generation is in progress and return PENDING
            if voice_id:
                # Prefer matching by current text_hash; if not found, relax to any PENDING for this voice_id
                pending_r = await db_session.execute(
                    select(VoiceLineAudio).where(
                        VoiceLineAudio.voice_line_id == voice_line_id,
                        VoiceLineAudio.voice_id == voice_id,
                        VoiceLineAudio.text_hash == tts_service.compute_text_hash(voice_line.text),
                        VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
                    ).order_by(VoiceLineAudio.created_at.desc()).limit(1)
                )
                pending_asset: VoiceLineAudio | None = pending_r.scalar_one_or_none()
                if not pending_asset:
                    pending_r_relaxed = await db_session.execute(
                        select(VoiceLineAudio).where(
                            VoiceLineAudio.voice_line_id == voice_line_id,
                            VoiceLineAudio.voice_id == voice_id,
                            VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
                        ).order_by(VoiceLineAudio.created_at.desc()).limit(1)
                    )
                    pending_asset = pending_r_relaxed.scalar_one_or_none()
            else:
                # Fallback: any PENDING for this voice line
                pending_r = await db_session.execute(
                    select(VoiceLineAudio).where(
                        VoiceLineAudio.voice_line_id == voice_line_id,
                        VoiceLineAudio.status == VoiceLineAudioStatusEnum.PENDING,
                    ).order_by(VoiceLineAudio.created_at.desc()).limit(1)
                )
                pending_asset: VoiceLineAudio | None = pending_r.scalar_one_or_none()

            if pending_asset:
                return JSONResponse(status_code=202, content={"status": VoiceLineAudioStatusEnum.PENDING.value})

            raise HTTPException(status_code=404, detail="No audio file found for this voice line")

        # Generate fresh signed URL
        signed_url = await tts_service.get_audio_url(asset.storage_path, expires_in)
        
        if not signed_url:
            raise HTTPException(status_code=500, detail="Failed to generate audio URL")
        
        return {"signed_url": signed_url, "expires_in": expires_in}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audio URL: {str(e)}")
