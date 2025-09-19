import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy import select

from app.langchain import ScenarioProcessor, SingleLineEnhancer, ScenarioState
from app.schemas.scenario import ScenarioCreateRequest, ScenarioCreateResponse, ScenarioResponse, VoiceLineResponse, VoiceLineAudioResponse
from app.core.auth import AuthUser
from app.repositories.profile_repository import ProfileRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.voice_line_repository import VoiceLineRepository
from app.services.profile_service import ProfileService
from app.core.database import AsyncSession
from app.core.logging import console_logger
from app.services.tts_service import TTSService
from app.services.audio_progress_service import AudioProgressService
from app.models.scenario import Scenario
from app.models.voice_line import VoiceLine
from app.core.utils.enums import VoiceLineTypeEnum
from app.services.cache_service import CacheService

class ScenarioService: 
    """Service for managing scenarios with LangChain processing"""

    def __init__(self, db_session: AsyncSession):
        self.profile_repository = ProfileRepository(db_session)
        self.profile_service = ProfileService(db_session)
        self.repository = ScenarioRepository(db_session)
        self.voice_line_repository = VoiceLineRepository(db_session)
        self.db_session = db_session
        self._stale_pending_seconds = int(os.getenv("TTS_PENDING_STALE_SECONDS", "120"))



    # ====== LangChain Invocations ======


    async def process_chat(self,
                           user: AuthUser,
                           scenario_create_request: ScenarioCreateRequest
                           ) -> Dict[str, Any]:
        

        state = ScenarioState(scenario_description=scenario_create_request.description)
        processor = ScenarioProcessor()

        result:Dict[str, Any] = await processor.process(state)

        state = ScenarioState(**result)
        created = await self.create_scenario_from_state(user, state)
        await self.profile_service.update_credits(user, -1, 0)
        
        return {
            "status": "complete",
            "scenario_id": created.scenario.id
        }


    async def enhance_voice_lines_with_feedback(self, user: AuthUser, voice_line_ids: List[int], 
                                              user_feedback: str) -> dict:
        """Enhance multiple voice lines based on user feedback"""
        
        console_logger.info(f"Enhancing {len(voice_line_ids)} voice lines with feedback")
        
        try:
            # Load voice lines with eager loading of relationships
            from app.repositories.voice_line_repository import VoiceLineRepository
            from app.models.voice_line_audio import VoiceLineAudio
            from sqlalchemy.orm import selectinload
            
            # Query voice lines with all needed relationships
            query = (
                select(VoiceLine)
                .join(Scenario)
                .where(VoiceLine.id.in_(voice_line_ids))
                .where(Scenario.user_id == user.id)
                .options(
                    selectinload(VoiceLine.audios),
                    selectinload(VoiceLine.scenario)
                )
                .order_by(VoiceLine.order_index)
            )
            result = await self.db_session.execute(query)
            voice_lines = result.scalars().all()
            
            if not voice_lines:
                raise ValueError("No voice lines found")
            
            # Enhance each voice line
            successful_enhancements = []
            failed_enhancements = []
            
            # Create TTSService instance once, outside the loop
            tts_service = TTSService()
            
            for voice_line in voice_lines:
                original_text = voice_line.text
                try:
                    # Use SingleLineEnhancer for individual lines
                    result = await SingleLineEnhancer.enhance(
                        voice_line_id=voice_line.id,
                        original_text=original_text,
                        voice_line_type=voice_line.type.value,
                        user_feedback=user_feedback,
                        scenario_analysis=voice_line.scenario.scenario_analysis
                    )
                    
                    # Update voice line if safe
                    if result["is_safe"]:
                        voice_line.text = result["enhanced_text"]
                        
                        # Delete existing audio files
                        # Query audios explicitly to avoid lazy loading
                        audio_query = await self.db_session.execute(
                            select(VoiceLineAudio).where(VoiceLineAudio.voice_line_id == voice_line.id)
                        )
                        audios = audio_query.scalars().all()
                        
                        for audio in audios:
                            if audio.storage_path:
                                await tts_service.delete_audio_file(audio.storage_path)
                            await self.db_session.delete(audio)
                        
                        # Add to successful enhancements with proper schema
                        successful_enhancements.append({
                            "voice_line_id": voice_line.id,
                            "original_text": original_text,
                            "enhanced_text": result["enhanced_text"],
                            "safety_passed": True,
                            "safety_issues": []
                        })
                    else:
                        # Add to failed enhancements with proper schema
                        failed_enhancements.append({
                            "voice_line_id": voice_line.id,
                            "original_text": original_text,
                            "enhanced_text": None,
                            "error": "Safety check failed",
                            "safety_passed": False,
                            "safety_issues": ["Content failed safety check"]
                        })
                        
                except Exception as e:
                    console_logger.error(f"Failed to enhance voice line {voice_line.id}: {str(e)}")
                    failed_enhancements.append({
                        "voice_line_id": voice_line.id,
                        "original_text": original_text,
                        "enhanced_text": None,
                        "error": str(e),
                        "safety_passed": False,
                        "safety_issues": []
                    })
            
            # Commit changes
            await self.db_session.commit()
            
            # Return response matching VoiceLineEnhancementResponse schema
            return {
                "success": len(successful_enhancements) > 0,
                "total_processed": len(voice_lines),
                "successful_count": len(successful_enhancements),
                "failed_count": len(failed_enhancements),
                "successful_enhancements": successful_enhancements,
                "failed_enhancements": failed_enhancements,
                "user_feedback": user_feedback
            }
                
        except Exception as e:
            console_logger.error(f"Enhancement failed: {str(e)}")
            await self.db_session.rollback()
            raise

    # ===== DRY helpers below =====

    async def create_scenario_from_state(self, user: AuthUser, state: ScenarioState) -> ScenarioCreateResponse:
        """Create a scenario from an already processed state"""
        console_logger.info(f"Creating scenario from state for user {user.id_str}")
        
        try:
            scenario = await self._persist_scenario_from_state(user, state)
            return ScenarioCreateResponse(
                scenario=await self._to_scenario_response(scenario, include_audio=False),
                processing_summary=self._build_processing_summary(state)
            )
        except Exception as e:
            console_logger.error(f"Failed to create scenario from state: {str(e)}")
            await self.db_session.rollback()
            raise

    def _scenario_payload_from_state(self, user: AuthUser, state: ScenarioState) -> dict:
        return {
            "user_id": user.id_str,
            "title": state.title,
            "description": state.scenario_description,
            "language": state.language,
            "target_name": state.target_name,
            "preferred_voice_id": None,
            "scenario_analysis": self._build_scenario_analysis(state),
            "was_rewritten": getattr(state, 'was_rewritten', False),
            "is_safe": state.safety.is_safe if state.safety else True,
            "is_not_safe_reason": state.safety.reasoning if state.safety and not state.safety.is_safe else None,
        }
    
    def _build_scenario_analysis(self, state: ScenarioState) -> Dict[str, Any]:
        """Build scenario_analysis JSON from state"""
        analysis = {}
        
        if state.analysis:
            analysis["analysis"] = {
                "persona_name": state.analysis.persona_name,
                "persona_gender": state.analysis.persona_gender,
                "company_service": state.analysis.company_service,
                "conversation_goals": state.analysis.conversation_goals,
                "believability_anchors": state.analysis.believability_anchors,
                "escalation_plan": state.analysis.escalation_plan,
                "cultural_context": state.analysis.cultural_context,
                "voice_hints": state.analysis.voice_hints
            }
        
        if state.safety:
            analysis["safety"] = {
                "issues": state.safety.issues,
                "recommendation": state.safety.recommendation,
                "reasoning": state.safety.reasoning,
                "confidence": state.safety.confidence
            }
        
        return analysis

    def _build_processing_summary(self, state: ScenarioState) -> dict:

        return {
            "was_rewritten": getattr(state, 'was_rewritten', False),
            "clarifications_used": len(getattr(state, 'clarifications', []) or []),
        }
    
    def _voice_lines_payload_from_state(self, state: ScenarioState) -> List[dict]:
        payloads: List[dict] = []
        order_index = 0
        for voice_type_str, lines in (state.tts_lines or {}).items():
            try:
                voice_type_enum = VoiceLineTypeEnum[voice_type_str]
            except KeyError:
                console_logger.error(f"Unknown voice type: {voice_type_str}")
                continue
            for text in lines:
                payloads.append({
                    "text": text,
                    "type": voice_type_enum,
                    "order_index": order_index
                })
                order_index += 1
        return payloads

    async def _to_scenario_response(self, scenario: Scenario, include_audio: bool = False) -> ScenarioResponse:
        """Convert a Scenario ORM object into ScenarioResponse"""
        voice_lines_response: List[VoiceLineResponse] = []

        # Batch sign preferred audios (if requested and available), with caching
        signed_map: Dict[str, Optional[str]] = {}
        if include_audio:
            storage_paths: List[str] = []
            for vl in scenario.voice_lines:
                if hasattr(vl, '_preferred_audio') and vl._preferred_audio and getattr(vl._preferred_audio, 'storage_path', None):
                    storage_paths.append(vl._preferred_audio.storage_path)
            if storage_paths:
                tts_service = TTSService()
                signed_map = await tts_service.get_audio_urls_batch(storage_paths, expires_in=3600)
        for vl in scenario.voice_lines:
            preferred_audio = None
            if include_audio and hasattr(vl, '_preferred_audio') and vl._preferred_audio:
                audio = vl._preferred_audio
                signed_url = signed_map.get(audio.storage_path) if audio.storage_path else None
                preferred_audio = VoiceLineAudioResponse(
                    id=audio.id,
                    voice_id=audio.voice_id,
                    storage_path=audio.storage_path,
                    signed_url=signed_url,
                    duration_ms=audio.duration_ms,
                    size_bytes=audio.size_bytes,
                    created_at=audio.created_at
                )

            voice_lines_response.append(VoiceLineResponse(
                id=vl.id,
                text=vl.text,
                type=vl.type,
                order_index=vl.order_index,
                created_at=vl.created_at,
                updated_at=vl.updated_at,
                preferred_audio=preferred_audio
            ))

        return ScenarioResponse(
            id=scenario.id,
            title=scenario.title,
            description=scenario.description,
            language=scenario.language,
            preferred_voice_id=scenario.preferred_voice_id,
            target_name=scenario.target_name,
            scenario_analysis=scenario.scenario_analysis,
            is_safe=scenario.is_safe,
            is_not_safe_reason=scenario.is_not_safe_reason,
            background_image_url=scenario.background_image_url,
            is_public=scenario.is_public,
            is_active=scenario.is_active,
            created_at=scenario.created_at,
            updated_at=scenario.updated_at,
            voice_lines=voice_lines_response
        )


    # ====== Database Operations ======

    async def get_scenario(self, user: AuthUser, scenario_id: int) -> ScenarioResponse:
        """Get a scenario by ID"""
        # Load audio for detail view - it needs to show play buttons
        scenario = await self.repository.get_scenario_by_id(scenario_id, user.id_str, load_audio=True)
        
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        return await self._to_scenario_response(scenario, include_audio=True)
    

    async def get_user_scenarios(self, user: AuthUser, limit: int = 50, offset: int = 0, only_active: bool = True) -> List[ScenarioResponse]:
        """Get all scenarios for a user"""
        scenarios = await self.repository.get_user_scenarios(user.id_str, limit, offset, only_active)
        responses: List[ScenarioResponse] = []
        for s in scenarios:
            responses.append(await self._to_scenario_response(s, include_audio=False))
        return responses


    async def update_preferred_voice(self, user: AuthUser, scenario_id: int, 
                                    preferred_voice_id: str) -> ScenarioResponse:
        """Update the preferred voice for a scenario"""
        
        # Load current scenario to capture existing active state
        current = await self.repository.get_scenario_by_id(scenario_id, user.id_str, load_audio=False)
        if not current:
            raise ValueError(f"Scenario {scenario_id} not found")

        was_active = current.is_active

        # Update preferred voice
        updated_scenario = await self.repository.update_scenario_preferred_voice(
            scenario_id, user.id_str, preferred_voice_id
        )
        if not updated_scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        # If the scenario was active, ensure the new voice has complete audio coverage; otherwise deactivate
        if was_active:
            status = await self.get_audio_generation_status(user, scenario_id)
            if not status.get("is_complete", False):
                # Deactivate when incomplete for the new voice
                updated_scenario.is_active = False
                await self.db_session.commit()

        # Return the updated scenario without audio - it's already loaded with voice_lines
        return await self._to_scenario_response(updated_scenario, include_audio=False)
    
    async def delete_scenario(self, user: AuthUser, scenario_id: int) -> None:
        """Delete a scenario and all its related data"""
        # First check if the scenario exists and belongs to the user
        scenario = await self.repository.get_scenario_by_id(scenario_id, user.id_str, load_audio=False)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found or access denied")
        
        # Delete the scenario (cascade will handle voice_lines and audio)
        await self.repository.delete_scenario(scenario_id, user.id_str)
        await self.db_session.commit()
        console_logger.info(f"Deleted scenario {scenario_id} for user {user.id_str}")

    async def _persist_scenario_from_state(self, user: AuthUser, state: ScenarioState) -> Scenario:
        """Persist scenario + voice lines using repository helpers."""
        scenario_data = self._scenario_payload_from_state(user, state)
        
        scenario = await self.repository.create_scenario(scenario_data)
        voice_lines_payload = self._voice_lines_payload_from_state(state)
        if voice_lines_payload:
            await self.voice_line_repository.add_voice_lines(scenario.id, voice_lines_payload)
        await self.db_session.commit()
        scenario = await self.repository.get_scenario_by_id(scenario.id, user.id_str, load_audio=False)
        return scenario
    
    async def set_active_status(self, user: AuthUser, scenario_id: int, is_active: bool) -> ScenarioResponse:
        """Set scenario active/inactive status"""
        console_logger.info(f"Setting scenario {scenario_id} active status to {is_active}")
        
        # Get scenario and verify ownership
        scenario = await self.repository.get_scenario_by_id(scenario_id, user.id_str, load_audio=True)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        # Check if scenario can be activated
        if is_active:
            # Check if scenario is safe
            if not scenario.is_safe:
                raise ValueError("Cannot activate unsafe scenario")
            
            # Check if all voice lines have audio
            audio_status = await self.get_audio_generation_status(user, scenario_id)
            if not audio_status["is_complete"]:
                raise ValueError("Cannot activate scenario without all audio files generated")
        
        # Update active status
        scenario.is_active = is_active
        await self.db_session.commit()
        
        return await self._to_scenario_response(scenario, include_audio=True)
    
    async def get_audio_generation_status(
        self,
        user: AuthUser,
        scenario_id: int,
        voice_id: Optional[str] = None,
    ) -> dict:
        """Get audio generation status for all voice lines"""
        from app.models.voice_line_audio import VoiceLineAudio
        from app.core.utils.enums import VoiceLineAudioStatusEnum
        from sqlalchemy import select, and_
        
        scenario = await self.repository.get_scenario_by_id(scenario_id, user.id_str, load_audio=False)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        total_voice_lines = len(scenario.voice_lines)
        generated_count = 0
        pending_count = 0
        failed_count = 0
        stale_pending_count = 0

        # Get all voice line IDs
        voice_line_ids = [vl.id for vl in scenario.voice_lines]

        lookup_voice_id = voice_id or scenario.preferred_voice_id
        cached_progress = None
        if lookup_voice_id:
            cached_progress = await AudioProgressService.get_progress(scenario_id, lookup_voice_id)
        if not cached_progress:
            cached_progress = await AudioProgressService.get_latest_progress(scenario_id)
            if cached_progress:
                lookup_voice_id = cached_progress.get("voice_id") or lookup_voice_id
        if cached_progress:
            counts = cached_progress.get("counts", {}) or {}
            generated_count = int(counts.get("ready", 0))
            failed_count = int(counts.get("failed", 0))
            pending_count = int(counts.get("pending", 0))
            stale_pending_count = 0  # Redis snapshot does not track staleness
            total_voice_lines = int(cached_progress.get("total", total_voice_lines))
            statuses_raw = cached_progress.get("statuses", {}) or {}
            line_statuses = {
                int(vl_id): status for vl_id, status in statuses_raw.items()
            }
            is_complete = (
                generated_count == total_voice_lines
                and failed_count == 0
                and total_voice_lines > 0
            )
            can_activate = scenario.is_safe and is_complete
            return {
                "total_voice_lines": total_voice_lines,
                "generated_count": generated_count,
                "pending_count": pending_count,
                "failed_count": failed_count,
                "stale_pending_count": stale_pending_count,
                "is_complete": is_complete,
                "can_activate": can_activate,
                "updated_at": cached_progress.get("updated_at"),
                "completed_at": cached_progress.get("completed_at"),
                "voice_id": lookup_voice_id,
                "line_statuses": line_statuses,
            }

        line_statuses: Dict[int, str] = {}

        if voice_line_ids and lookup_voice_id:
            # Query for audios that match the preferred voice
            audio_query = (
                select(VoiceLineAudio)
                .where(
                    and_(
                        VoiceLineAudio.voice_line_id.in_(voice_line_ids),
                        VoiceLineAudio.voice_id == lookup_voice_id
                    )
                )
            )
            
            audio_result = await self.db_session.execute(audio_query)
            audios = audio_result.scalars().all()
            now = datetime.now(timezone.utc)
            stale_cutoff = now - timedelta(seconds=self._stale_pending_seconds)

            # Count by status
            for audio in audios:
                if audio.status == VoiceLineAudioStatusEnum.READY:
                    generated_count += 1
                    line_statuses[audio.voice_line_id] = VoiceLineAudioStatusEnum.READY.name
                elif audio.status == VoiceLineAudioStatusEnum.PENDING:
                    pending_count += 1
                    if audio.updated_at and audio.updated_at < stale_cutoff:
                        stale_pending_count += 1
                    line_statuses.setdefault(audio.voice_line_id, VoiceLineAudioStatusEnum.PENDING.name)
                elif audio.status == VoiceLineAudioStatusEnum.FAILED:
                    failed_count += 1
                    line_statuses[audio.voice_line_id] = VoiceLineAudioStatusEnum.FAILED.name

            # Add entries for voice lines without audio yet
            for vl_id in voice_line_ids:
                if vl_id not in line_statuses:
                    line_statuses[vl_id] = VoiceLineAudioStatusEnum.PENDING.name

        is_complete = generated_count == total_voice_lines
        can_activate = scenario.is_safe and is_complete

        return {
            "total_voice_lines": total_voice_lines,
            "generated_count": generated_count,
            "pending_count": pending_count,
            "failed_count": failed_count,
            "stale_pending_count": stale_pending_count,
            "is_complete": is_complete,
            "can_activate": can_activate,
            "voice_id": lookup_voice_id,
            "line_statuses": line_statuses if voice_line_ids else {},
        }
    
    async def get_public_scenarios(self) -> List[Scenario]:
        """Get public scenarios"""
        scenarios: List[Scenario] = await self.repository.get_public_scenarios()
        scenarios_responses: List[ScenarioResponse] = []
        for s in scenarios:
            s_response = await self._to_scenario_response(s, include_audio=False)
            scenarios_responses.append(s_response)
        return scenarios_responses
    
    async def get_public_scenario_detail(self, scenario_id: int) -> ScenarioResponse:
        """Get a single public scenario with signed audio for preferred voice"""
        scenario = await self.repository.get_public_scenario_by_id(scenario_id, load_audio=True)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        return await self._to_scenario_response(scenario, include_audio=True)
    
    
