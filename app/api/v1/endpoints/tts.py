# app/api/v1/endpoints/tts.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.services.tts_service import TTSService
from app.repositories.scenario_repository import ScenarioRepository
from app.core.utils.enums import ElevenLabsVoiceIdEnum
from app.schemas.tts import SingleTTSRequest, BatchTTSRequest, ScenarioTTSRequest, RegenerateTTSRequest, TTSResult, TTSResponse, VoiceListResponse

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
        
        # Generate TTS
        tts_service = TTSService()
        success, signed_url, storage_path, error_msg = await tts_service.generate_and_store_audio(
            text=voice_line.text,
            voice_line_id=request.voice_line_id,
            user_id=str(user.id),
            voice_id=request.voice_id,
            language=request.language,
            gender=request.gender,
            model=request.model
        )
        
        if success:
            # Update voice line with storage info
            await repository.update_voice_line_storage(
                request.voice_line_id, signed_url, storage_path, user.id
            )
            await repository.commit()
        
        return TTSResult(
            voice_line_id=request.voice_line_id,
            success=success,
            signed_url=signed_url,
            storage_path=storage_path,
            error_message=error_msg
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
                success, signed_url, storage_path, error_msg = await tts_service.generate_and_store_audio(
                    text=voice_line.text,
                    voice_line_id=voice_line.id,
                    user_id=str(user.id),
                    voice_id=request.voice_id,
                    language=request.language,
                    gender=request.gender,
                    model=request.model
                )
                
                if success:
                    # Update voice line with storage info
                    await repository.update_voice_line_storage(
                        voice_line.id, signed_url, storage_path, user.id
                    )
                
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
        
        # Commit all successful updates
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
                success, signed_url, storage_path, error_msg = await tts_service.generate_and_store_audio(
                    text=voice_line.text,
                    voice_line_id=voice_line.id,
                    user_id=str(user.id),
                    voice_id=request.voice_id,
                    language=scenario_language,
                    gender=request.gender,
                    model=request.model
                )
                
                if success:
                    # Update voice line with storage info
                    await repository.update_voice_line_storage(
                        voice_line.id, signed_url, storage_path, user.id
                    )
                
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
        
        # Commit all successful updates
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
        
        # Regenerate TTS
        tts_service = TTSService()
        success, new_signed_url, new_storage_path, error_msg = await tts_service.regenerate_audio(
            old_storage_path=voice_line.storage_path,
            new_text=voice_line.text,
            voice_line_id=request.voice_line_id,
            user_id=str(user.id),
            voice_id=request.voice_id,
            language=request.language,
            gender=request.gender,
            model=request.model
        )
        
        if success:
            # Update voice line with new storage info
            await repository.update_voice_line_storage(
                request.voice_line_id, new_signed_url, new_storage_path, user.id
            )
            await repository.commit()
        
        return TTSResult(
            voice_line_id=request.voice_line_id,
            success=success,
            signed_url=new_signed_url,
            storage_path=new_storage_path,
            error_message=error_msg
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await repository.rollback()
        raise HTTPException(status_code=500, detail=f"TTS regeneration failed: {str(e)}")

@router.get("/audio-url/{voice_line_id}")
async def get_voice_line_audio_url(
    voice_line_id: int,
    expires_in: int = 3600,  # 1 hour default
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
        
        if not voice_line.storage_path:
            raise HTTPException(status_code=404, detail="No audio file found for this voice line")
        
        # Generate fresh signed URL
        tts_service = TTSService()
        signed_url = await tts_service.get_audio_url(voice_line.storage_path, expires_in)
        
        if not signed_url:
            raise HTTPException(status_code=500, detail="Failed to generate audio URL")
        
        return {"signed_url": signed_url, "expires_in": expires_in}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audio URL: {str(e)}")
