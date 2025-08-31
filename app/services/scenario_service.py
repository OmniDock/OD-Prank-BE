from app.langchain import ScenarioProcessor, EnhancementProcessor, SingleLineEnhancer, ScenarioState
from app.schemas.scenario import ScenarioCreateRequest, ScenarioCreateResponse, ScenarioResponse, VoiceLineResponse, VoiceLineAudioResponse
from app.core.auth import AuthUser
from app.repositories.scenario_repository import ScenarioRepository
from app.repositories.voice_line_repository import VoiceLineRepository
from app.core.database import AsyncSession
from app.core.logging import console_logger
from app.services.tts_service import TTSService
from app.models.scenario import Scenario
from app.models.voice_line import VoiceLine
from app.core.utils.enums import VoiceLineTypeEnum
from typing import List, Optional, Dict, Any
from sqlalchemy import select


class ScenarioService: 
    """Service for managing scenarios with LangChain processing"""

    def __init__(self, db_session: AsyncSession):
        self.repository = ScenarioRepository(db_session)
        self.voice_line_repository = VoiceLineRepository(db_session)
        self.db_session = db_session

    async def create_scenario(self, user: AuthUser, scenario_data: ScenarioCreateRequest) -> ScenarioCreateResponse:
        """Create and process a scenario, then save to database"""
        console_logger.info(f"Creating scenario '{scenario_data.title}' for user {user.id}")
        
        try:
            # Step 1: Process scenario with LangChain
            processor = ScenarioProcessor()
            state = ScenarioState(scenario_data=scenario_data)
            
            # Process the scenario (may include clarification loop)
            result = await processor.process(state)
            
            # Normalize to state
            state = ScenarioState(**result) if isinstance(result, dict) else result
            
            # Step 2: Persist scenario + lines (DRY)
            scenario = await self._persist_scenario_from_state(user, state)

            # Step 3: Build response
            return ScenarioCreateResponse(
                scenario=await self._to_scenario_response(scenario, include_audio=False),
                processing_summary=self._build_processing_summary(state)
            )
            
        except Exception as e:
            console_logger.error(f"Failed to create scenario: {str(e)}")
            await self.repository.rollback()
            raise
    
    def _build_scenario_analysis(self, state: ScenarioState) -> Dict[str, Any]:
        """Build scenario_analysis JSON from state"""
        analysis = {}
        
        if state.analysis:
            analysis["analysis"] = {
                "persona_name": state.analysis.persona_name,
                "company_service": state.analysis.company_service,
                "conversation_goals": state.analysis.conversation_goals,
                "believability_anchors": state.analysis.believability_anchors,
                "escalation_plan": state.analysis.escalation_plan,
                "cultural_context": state.analysis.cultural_context,
                "voice_hints": state.analysis.voice_hints
            }
        
        if state.quality:
            analysis["quality"] = {
                "seriousness": state.quality.seriousness,
                "believability": state.quality.believability,
                "subtle_emotion": state.quality.subtle_emotion,
                "notes": state.quality.notes
            }
        
        if state.safety:
            analysis["safety"] = {
                "issues": state.safety.issues,
                "recommendation": state.safety.recommendation,
                "reasoning": state.safety.reasoning,
                "confidence": state.safety.confidence
            }
        
        return analysis
    
    async def get_scenario(self, user: AuthUser, scenario_id: int) -> ScenarioResponse:
        """Get a scenario by ID"""
        scenario = await self.repository.get_scenario_by_id(scenario_id, user.id_str)
        
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        return await self._to_scenario_response(scenario, include_audio=True)
    
    async def get_user_scenarios(self, user: AuthUser, limit: int = 50, offset: int = 0) -> List[ScenarioResponse]:
        """Get all scenarios for a user"""
        scenarios = await self.repository.get_user_scenarios(user.id_str, limit, offset)
        responses: List[ScenarioResponse] = []
        for s in scenarios:
            responses.append(await self._to_scenario_response(s, include_audio=False))
        return responses

    async def enhance_voice_lines_with_feedback(self, user: AuthUser, voice_line_ids: List[int], 
                                              user_feedback: str) -> dict:
        """Enhance multiple voice lines based on user feedback"""
        
        console_logger.info(f"Enhancing {len(voice_line_ids)} voice lines with feedback")
        
        try:
            # Load voice lines via repository with RLS check
            from app.repositories.voice_line_repository import VoiceLineRepository
            voice_lines = await self.voice_line_repository.get_voice_lines_by_ids_with_user_check(
                voice_line_ids, user.id_str
            )
            
            if not voice_lines:
                raise ValueError("No voice lines found")
            
            # Check ownership
            for vl in voice_lines:
                if str(vl.scenario.user_id) != user.id_str:
                    raise ValueError(f"Voice line {vl.id} does not belong to user")
            
            # Enhance each voice line
            successful_enhancements = []
            failed_enhancements = []
            
            for voice_line in voice_lines:
                try:
                    # Use SingleLineEnhancer for individual lines
                    result = await SingleLineEnhancer.enhance(
                        voice_line_id=voice_line.id,
                        original_text=voice_line.text,
                        voice_line_type=voice_line.type.value,
                        user_feedback=user_feedback,
                        scenario_analysis=voice_line.scenario.scenario_analysis
                    )
                    
                    # Update voice line if safe
                    if result["is_safe"]:
                        voice_line.text = result["enhanced_text"]
                        
                        # Delete existing audio files
                        for audio in voice_line.audios:
                            if audio.storage_path:
                                tts_service = TTSService()
                                await tts_service.delete_audio_file(audio.storage_path)
                            await self.db_session.delete(audio)
                        
                            successful_enhancements.append({
                                "voice_line_id": voice_line.id,
                            "new_text": result["enhanced_text"]
                            })
                    else:
                        failed_enhancements.append({
                            "voice_line_id": voice_line.id,
                            "reason": "Safety check failed"
                        })
                        
                except Exception as e:
                    console_logger.error(f"Failed to enhance voice line {voice_line.id}: {str(e)}")
                    failed_enhancements.append({
                        "voice_line_id": voice_line.id,
                        "reason": str(e)
                    })
            
            # Commit changes
            await self.db_session.commit()
            
            return {
                "successful_enhancements": successful_enhancements,
                "failed_enhancements": failed_enhancements,
                "total_processed": len(voice_lines)
            }
                
        except Exception as e:
            console_logger.error(f"Enhancement failed: {str(e)}")
            await self.db_session.rollback()
            raise

    async def create_scenario_from_state(self, user: AuthUser, state: ScenarioState) -> ScenarioCreateResponse:
        """Create a scenario from an already processed state"""
        console_logger.info(f"Creating scenario from state for user {user.id}")
        
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

    async def enhance_full_scenario(self, user: AuthUser, scenario_id: int, 
                                   user_feedback: str) -> ScenarioResponse:
        """Enhance all voice lines in a scenario"""
        console_logger.info(f"Enhancing full scenario {scenario_id}")
        
        try:
            # Load scenario
            scenario = await self.repository.get_scenario_by_id(scenario_id, user.id_str)
            if not scenario:
                raise ValueError(f"Scenario {scenario_id} not found")
            
            # Use EnhancementProcessor for full scenario
            from app.langchain import EnhancementProcessor, ScenarioState
            
            # Build state from existing scenario
            state = ScenarioState(
                scenario_data=ScenarioCreateRequest(
                    title=scenario.title,
                    description=scenario.description,
                    language=scenario.language,
                    target_name=scenario.target_name,
                    preferred_voice_id=scenario.preferred_voice_id
                ),
                clarifying_questions=scenario.clarifying_questions,
                clarifications=scenario.clarifications,
                analysis=scenario.scenario_analysis.get("analysis") if scenario.scenario_analysis else None,
                tts_lines={}
            )
            
            # Rebuild tts_lines from voice lines
            for vl in scenario.voice_lines:
                vl_type = vl.type.value
                if vl_type not in state.tts_lines:
                    state.tts_lines[vl_type] = []
                state.tts_lines[vl_type].append(vl.text)
            
            # Enhance
            enhancer = EnhancementProcessor()
            enhanced_state = await enhancer.enhance_scenario(state, user_feedback)
            
            # Update voice lines
            for vl in scenario.voice_lines:
                vl_type = vl.type.value
                if vl_type in enhanced_state.tts_lines:
                    type_lines = enhanced_state.tts_lines[vl_type]
                    # Find corresponding enhanced line by position
                    type_index = [v for v in scenario.voice_lines if v.type.value == vl_type].index(vl)
                    if type_index < len(type_lines):
                        vl.text = type_lines[type_index]
                        
                        # Delete existing audio
                        # Query audios explicitly to avoid lazy loading
                        from app.models.voice_line_audio import VoiceLineAudio
                        audio_query = await self.db_session.execute(
                            select(VoiceLineAudio).where(VoiceLineAudio.voice_line_id == vl.id)
                        )
                        audios = audio_query.scalars().all()
                        
                        for audio in audios:
                            if audio.storage_path:
                                tts_service = TTSService()
                                await tts_service.delete_audio_file(audio.storage_path)
                            await self.db_session.delete(audio)
            
            # Update metadata
            if not scenario.scenario_analysis:
                scenario.scenario_analysis = {}
            scenario.scenario_analysis["last_enhancement"] = {
                "feedback": user_feedback,
                "changes": getattr(enhanced_state, 'enhancement_changes', [])
            }
            
            await self.db_session.commit()
            await self.db_session.refresh(scenario)
            
            return await self.get_scenario(user, scenario_id)
                
        except Exception as e:
            console_logger.error(f"Failed to enhance scenario: {str(e)}")
            await self.db_session.rollback()
            raise

    async def update_preferred_voice(self, user: AuthUser, scenario_id: int, 
                                    preferred_voice_id: str) -> ScenarioResponse:
        """Update the preferred voice for a scenario"""
        
        scenario = await self.repository.get_scenario_by_id(scenario_id, user.id_str)
        
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        scenario.preferred_voice_id = preferred_voice_id
        await self.db_session.commit()
        await self.db_session.refresh(scenario)
        
        return await self.get_scenario(user, scenario_id)

    async def _delete_voice_line_audios(self, voice_line_id: int):
        """Delete all audio files for a voice line"""
        from app.models.voice_line_audio import VoiceLineAudio
        from sqlalchemy import select
        
        result = await self.db_session.execute(
            select(VoiceLineAudio).where(VoiceLineAudio.voice_line_id == voice_line_id)
        )
        audios = result.scalars().all()
        
        tts_service = TTSService()
        for audio in audios:
            if audio.storage_path:
                await tts_service.delete_audio_file(audio.storage_path)
            await self.db_session.delete(audio)
        
        await self.db_session.commit()

    # ===== DRY helpers below =====

    def _scenario_payload_from_state(self, user: AuthUser, state: ScenarioState) -> dict:
        return {
            "user_id": user.id,
            "title": state.scenario_data.title,
            "description": state.scenario_data.description,
            "language": state.scenario_data.language,
            "target_name": state.scenario_data.target_name,
            "preferred_voice_id": getattr(state.scenario_data, 'preferred_voice_id', None),
            "scenario_analysis": self._build_scenario_analysis(state),
            "clarifying_questions": state.clarifying_questions,
            "clarifications": state.clarifications,
            "was_rewritten": getattr(state, 'was_rewritten', False),
            "is_safe": state.safety.is_safe if state.safety else True,
            "is_not_safe_reason": state.safety.reasoning if state.safety and not state.safety.is_safe else None,
            "is_public": False,
            "is_active": True
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

    async def _persist_scenario_from_state(self, user: AuthUser, state: ScenarioState) -> Scenario:
        """Persist scenario + voice lines using repository helpers"""
        scenario_data = self._scenario_payload_from_state(user, state)
        scenario = await self.repository.create_scenario(scenario_data)
        voice_lines_payload = self._voice_lines_payload_from_state(state)
        if voice_lines_payload:
            await self.voice_line_repository.add_voice_lines(scenario.id, voice_lines_payload)
        await self.db_session.commit()
        await self.db_session.refresh(scenario)
        return scenario

    async def _to_scenario_response(self, scenario: Scenario, include_audio: bool = False) -> ScenarioResponse:
        """Convert a Scenario ORM object into ScenarioResponse"""
        voice_lines_response: List[VoiceLineResponse] = []
        for vl in scenario.voice_lines:
            preferred_audio = None
            if include_audio and hasattr(vl, '_preferred_audio') and vl._preferred_audio:
                audio = vl._preferred_audio
                signed_url = None
                if audio.storage_path:
                    try:
                        tts_service = TTSService()
                        signed_url = await tts_service.get_audio_url(audio.storage_path)
                    except Exception as e:
                        console_logger.warning(f"Failed to generate signed URL for audio {audio.id}: {str(e)}")
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
            is_public=scenario.is_public,
            is_active=scenario.is_active,
            created_at=scenario.created_at,
            updated_at=scenario.updated_at,
            voice_lines=voice_lines_response
        )

    def _build_processing_summary(self, state: ScenarioState) -> dict:
        return {
            "was_rewritten": getattr(state, 'was_rewritten', False),
            "clarifications_used": len(getattr(state, 'clarifications', []) or []),
            "quality_score": (
                {
                    "seriousness": state.quality.seriousness if state and state.quality else None,
                    "believability": state.quality.believability if state and state.quality else None,
                    "subtle_emotion": state.quality.subtle_emotion if state and state.quality else None
                } if state and state.quality else None
            )
        }