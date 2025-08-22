# app/api/v1/endpoints/tts.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.services.tts_service import TTSService
from app.repositories.scenario_repository import ScenarioRepository
from app.core.utils.enums import ElevenLabsVoiceIdEnum, VoiceLineAudioStatusEnum
from app.schemas.tts import SingleTTSRequest, BatchTTSRequest, ScenarioTTSRequest, RegenerateTTSRequest, TTSResult, TTSResponse, VoiceListResponse
from sqlalchemy import select
from app.models.voice_line_audio import VoiceLineAudio

router = APIRouter(tags=["tts"])


# Endpoints
@router.get("/voices", response_model=VoiceListResponse)
async def get_available_voices():
    """Get list of available voices organized by language and gender"""
    voices = {
        "english": {
            "male": [
                {"id": ElevenLabsVoiceIdEnum.ENGLISH_MALE_JARNATHAN.value, "name": "Jarnathan", "description": "Well-rounded, young American voice"},
            ],
            "female": [
                {"id": ElevenLabsVoiceIdEnum.ENGLISH_FEMALE_CHELSEA.value, "name": "Chelsea", "description": "Pleasant, British, engaging"},
            ]
        },
        "german": {
            "male": [
                {"id": ElevenLabsVoiceIdEnum.GERMAN_MALE_FELIX.value, "name": "Felix", "description": "Strong, documentary style"},
            ],
            "female": [
                {"id": ElevenLabsVoiceIdEnum.GERMAN_FEMALE_SUSI.value, "name": "Susi", "description": "Soft, news presenter style"},
            ]
        }
    }
    
    return VoiceListResponse(voices=voices)

@router.post("/generate/single", response_model=TTSResult)
async def generate_single_voice_line(
    request: SingleTTSRequest,
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
        selected_voice_id = tts_service.select_voice_id(request.voice_id, request.language, request.gender)
        voice_settings = tts_service.default_voice_settings()
        content_hash = tts_service.compute_content_hash(voice_line.text, selected_voice_id, request.model, voice_settings)

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

        # Generate new audio
        success, signed_url, storage_path, error_msg = await tts_service.generate_and_store_audio(
            text=voice_line.text,
            voice_line_id=request.voice_line_id,
            user_id=str(user.id),
            voice_id=selected_voice_id,
            language=request.language,
            gender=request.gender,
            model=request.model,
            voice_settings=voice_settings,
        )

        if success and storage_path:
            # Persist new asset (history)
            asset = VoiceLineAudio(
                voice_line_id=request.voice_line_id,
                voice_id=selected_voice_id,
                gender=request.gender,
                model_id=request.model,
                voice_settings=voice_settings,
                storage_path=storage_path,
                duration_ms=None,
                size_bytes=None,
                text_hash=tts_service.compute_text_hash(voice_line.text),
                settings_hash=tts_service.compute_settings_hash(selected_voice_id, request.model, voice_settings),
                content_hash=content_hash,
                status=VoiceLineAudioStatusEnum.READY,
                error=None,
            )
            db_session.add(asset)
            await repository.commit()

        return TTSResult(
            voice_line_id=request.voice_line_id,
            success=success,
            signed_url=signed_url,
            storage_path=storage_path,
            error_message=error_msg,
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
        
        # Process each voice line
        for voice_line in voice_lines:
            try:
                selected_voice_id = tts_service.select_voice_id(request.voice_id, request.language, request.gender)
                voice_settings = tts_service.default_voice_settings()
                content_hash = tts_service.compute_content_hash(voice_line.text, selected_voice_id, request.model, voice_settings)

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

                success, signed_url, storage_path, error_msg = await tts_service.generate_and_store_audio(
                    text=voice_line.text,
                    voice_line_id=voice_line.id,
                    user_id=str(user.id),
                    voice_id=selected_voice_id,
                    language=request.language,
                    gender=request.gender,
                    model=request.model,
                    voice_settings=voice_settings,
                )
                
                if success and storage_path:
                    asset = VoiceLineAudio(
                        voice_line_id=voice_line.id,
                        voice_id=selected_voice_id,
                        gender=request.gender,
                        model_id=request.model,
                        voice_settings=voice_settings,
                        storage_path=storage_path,
                        duration_ms=None,
                        size_bytes=None,
                        text_hash=tts_service.compute_text_hash(voice_line.text),
                        settings_hash=tts_service.compute_settings_hash(selected_voice_id, request.model, voice_settings),
                        content_hash=content_hash,
                        status=VoiceLineAudioStatusEnum.READY,
                        error=None,
                    )
                    db_session.add(asset)
                
                results.append(TTSResult(
                    voice_line_id=voice_line.id,
                    success=success,
                    signed_url=signed_url,
                    storage_path=storage_path,
                    error_message=error_msg
                ))
                
            except Exception as e:
                results.append(TTSResult(
                    voice_line_id=voice_line.id,
                    success=False,
                    error_message=f"Generation failed: {str(e)}"
                ))
        
        # Commit all successful asset inserts
        await repository.commit()
        
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
        
        # Use scenario language if not specified in request
        scenario_language = request.language or scenario.language
        
        # Process each voice line
        for voice_line in voice_lines:
            try:
                selected_voice_id = tts_service.select_voice_id(request.voice_id, scenario_language, request.gender)
                voice_settings = tts_service.default_voice_settings()
                content_hash = tts_service.compute_content_hash(voice_line.text, selected_voice_id, request.model, voice_settings)

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

                success, signed_url, storage_path, error_msg = await tts_service.generate_and_store_audio(
                    text=voice_line.text,
                    voice_line_id=voice_line.id,
                    user_id=str(user.id),
                    voice_id=selected_voice_id,
                    language=scenario_language,
                    gender=request.gender,
                    model=request.model,
                    voice_settings=voice_settings,
                )
                
                if success and storage_path:
                    asset = VoiceLineAudio(
                        voice_line_id=voice_line.id,
                        voice_id=selected_voice_id,
                        gender=request.gender,
                        model_id=request.model,
                        voice_settings=voice_settings,
                        storage_path=storage_path,
                        duration_ms=None,
                        size_bytes=None,
                        text_hash=tts_service.compute_text_hash(voice_line.text),
                        settings_hash=tts_service.compute_settings_hash(selected_voice_id, request.model, voice_settings),
                        content_hash=content_hash,
                        status=VoiceLineAudioStatusEnum.READY,
                        error=None,
                    )
                    db_session.add(asset)
                
                results.append(TTSResult(
                    voice_line_id=voice_line.id,
                    success=success,
                    signed_url=signed_url,
                    storage_path=storage_path,
                    error_message=error_msg
                ))
                
            except Exception as e:
                results.append(TTSResult(
                    voice_line_id=voice_line.id,
                    success=False,
                    error_message=f"Generation failed: {str(e)}"
                ))
        
        # Commit all successful asset inserts
        await repository.commit()
        
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
        selected_voice_id = tts_service.select_voice_id(request.voice_id, request.language, request.gender)
        voice_settings = tts_service.default_voice_settings()
        content_hash = tts_service.compute_content_hash(voice_line.text, selected_voice_id, request.model, voice_settings)

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

        success, new_signed_url, new_storage_path, error_msg = await tts_service.generate_and_store_audio(
            text=voice_line.text,
            voice_line_id=request.voice_line_id,
            user_id=str(user.id),
            voice_id=selected_voice_id,
            language=request.language,
            gender=request.gender,
            model=request.model,
            voice_settings=voice_settings,
        )

        if success and new_storage_path:
            asset = VoiceLineAudio(
                voice_line_id=request.voice_line_id,
                voice_id=selected_voice_id,
                gender=request.gender,
                model_id=request.model,
                voice_settings=voice_settings,
                storage_path=new_storage_path,
                duration_ms=None,
                size_bytes=None,
                text_hash=tts_service.compute_text_hash(voice_line.text),
                settings_hash=tts_service.compute_settings_hash(selected_voice_id, request.model, voice_settings),
                content_hash=content_hash,
                status=VoiceLineAudioStatusEnum.READY,
                error=None,
            )
            db_session.add(asset)
            await repository.commit()

        return TTSResult(
            voice_line_id=request.voice_line_id,
            success=success,
            signed_url=new_signed_url,
            storage_path=new_storage_path,
            error_message=error_msg,
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
    user: AuthUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """Get a fresh signed URL for accessing voice line audio"""
    try:
        repository = ScenarioRepository(db_session)
        
        # Verify user owns the voice line
        voice_line = await repository.get_voice_line_by_id_with_user_check(voice_line_id, user.id)
        
        if not voice_line:
            raise HTTPException(status_code=404, detail="Voice line not found or access denied")
        
        # Find latest READY asset for this voice line
        r = await db_session.execute(
            select(VoiceLineAudio).where(
                VoiceLineAudio.voice_line_id == voice_line_id,
                VoiceLineAudio.status == VoiceLineAudioStatusEnum.READY,
            ).order_by(VoiceLineAudio.created_at.desc()).limit(1)
        )
        asset: VoiceLineAudio | None = r.scalar_one_or_none()
        if not asset or not asset.storage_path:
            raise HTTPException(status_code=404, detail="No audio file found for this voice line")

        # Generate fresh signed URL
        tts_service = TTSService()
        signed_url = await tts_service.get_audio_url(asset.storage_path, expires_in)
        
        if not signed_url:
            raise HTTPException(status_code=500, detail="Failed to generate audio URL")
        
        return {"signed_url": signed_url, "expires_in": expires_in}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audio URL: {str(e)}")
