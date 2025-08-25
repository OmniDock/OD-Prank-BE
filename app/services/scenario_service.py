from app.langchain.scenarios.initial_processor import InitialScenarioProcessor
from app.langchain.scenarios.state import ScenarioProcessorState, VoiceLineState
from app.schemas.scenario import ScenarioCreateRequest, ScenarioCreateResponse, ScenarioResponse, VoiceLineResponse, VoiceLineAudioResponse
from app.core.auth import AuthUser
from app.repositories.scenario_repository import ScenarioRepository
from app.core.database import AsyncSession
from app.core.logging import console_logger
from app.services.tts_service import TTSService
from typing import List, Optional
from pprint import pprint 

class ScenarioService: 

    def __init__(self, db_session: AsyncSession):
        self.repository = ScenarioRepository(db_session)


    async def create_scenario(self, user: AuthUser, scenario_data: ScenarioCreateRequest) -> ScenarioCreateResponse:
        """Create and process a scenario, then save to database"""
        console_logger.info(f"Creating scenario '{scenario_data.title}' for user {user.id}")
        
        try:
            # Step 1: Process scenario with LangChain
            initial_processor = InitialScenarioProcessor.with_default_counts()
            results = await initial_processor.process_scenario(scenario_data)

            # Step 2: Determine safety status from results
            is_safe = results['overall_safety_check'].is_safe
            # Use overall safety issues if available, otherwise fall back to initial safety issues
            all_safety_issues = results['overall_safety_check'].issues if results['overall_safety_check'].issues else results['initial_safety_check'].issues
            safety_issues = "; ".join(all_safety_issues) if all_safety_issues else None
            
            # Step 3: Create scenario in database
            scenario_db_data = {
                "user_id": user.id,
                "title": scenario_data.title,
                "description": scenario_data.description,
                "language": scenario_data.language,
                "target_name": scenario_data.target_name,
                "scenario_analysis": results['scenario_analysis'].model_dump() if results['scenario_analysis'] else None,
                "is_safe": is_safe,
                "is_not_safe_reason": safety_issues,
                "is_public": False,  # Default to private
                "is_active": True
            }
            
            scenario = await self.repository.create_scenario(scenario_db_data)
            
            # Step 4: Extract and save voice lines
            voice_lines_data = self._extract_voice_lines_from_results(results)
            voice_lines = await self.repository.add_voice_lines(scenario.id, voice_lines_data)
            
            # Step 5: Commit transaction
            await self.repository.commit()
            
            # Step 6: Get complete scenario with voice lines for response
            complete_scenario = await self.repository.get_scenario_by_id(scenario.id, user.id)
            
            # Step 7: Create processing summary
            processing_summary = {
                "initial_safety_check": results['initial_safety_check'],
                "overall_safety_check": results['overall_safety_check'],
                "scenario_analysis": results['scenario_analysis'],
                "total_voice_lines_generated": len(voice_lines_data),
                "voice_line_counts": {
                    voice_type: len([vl for vl in voice_lines_data if vl['type'] == voice_type])
                    for voice_type in results['target_counts'].keys()
                }
            }
            
            console_logger.info(f"Successfully created scenario {scenario.id} with {len(voice_lines)} voice lines")
            
            return ScenarioCreateResponse(
                scenario=ScenarioResponse.model_validate(complete_scenario),
                processing_summary=processing_summary
            )
            
        except Exception as e:
            console_logger.error(f"Failed to create scenario: {str(e)}")
            await self.repository.rollback()
            raise
    
    
    def _extract_voice_lines_from_results(self, results: ScenarioProcessorState) -> List[dict]:
        """Extract voice lines from processing results and convert to database format"""
        voice_lines_data = []
        
        # Extract from each voice line type
        for voice_line_state in results['opening_voice_lines']:
            voice_lines_data.append({
                "text": voice_line_state.text,
                "type": voice_line_state.type.value,
            })
        
        for voice_line_state in results['question_voice_lines']:
            voice_lines_data.append({
                "text": voice_line_state.text,
                "type": voice_line_state.type.value,
            })
        
        for voice_line_state in results['response_voice_lines']:
            voice_lines_data.append({
                "text": voice_line_state.text,
                "type": voice_line_state.type.value,
            })
        
        for voice_line_state in results['closing_voice_lines']:
            voice_lines_data.append({
                "text": voice_line_state.text,
                "type": voice_line_state.type.value,
            })
        
        console_logger.info(f"Extracted {len(voice_lines_data)} voice lines for database storage")
        return voice_lines_data
    
    
    async def get_scenario(self, user: AuthUser, scenario_id: int) -> ScenarioResponse:
        """Get a scenario by ID with preferred voice audios if available"""
        scenario = await self.repository.get_scenario_by_id(scenario_id, user.id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found or access denied")
        
        # Convert to dict for manipulation
        scenario_dict = {
            "id": scenario.id,
            "title": scenario.title,
            "description": scenario.description,
            "language": scenario.language,
            "preferred_voice_id": scenario.preferred_voice_id,
            "target_name": scenario.target_name,
            "scenario_analysis": scenario.scenario_analysis,
            "is_safe": scenario.is_safe,
            "is_not_safe_reason": scenario.is_not_safe_reason,
            "is_public": scenario.is_public,
            "is_active": scenario.is_active,
            "created_at": scenario.created_at,
            "updated_at": scenario.updated_at,
            "voice_lines": []
        }
        
        # Process voice lines and include audio information if available
        tts_service = TTSService() if scenario.preferred_voice_id else None
        
        for voice_line in scenario.voice_lines:
            voice_line_dict = {
                "id": voice_line.id,
                "text": voice_line.text,
                "type": voice_line.type,
                "order_index": voice_line.order_index,
                "created_at": voice_line.created_at,
                "updated_at": voice_line.updated_at,
                "preferred_audio": None
            }
            
            # Check if this voice line has a preferred audio attached
            if hasattr(voice_line, '_preferred_audio') and voice_line._preferred_audio and tts_service:
                audio = voice_line._preferred_audio
                try:
                    # Generate signed URL for the audio
                    signed_url = await tts_service.get_audio_url(audio.storage_path)
                    if signed_url:
                        voice_line_dict["preferred_audio"] = {
                            "id": audio.id,
                            "voice_id": audio.voice_id,
                            "storage_path": audio.storage_path,
                            "signed_url": signed_url,
                            "duration_ms": audio.duration_ms,
                            "size_bytes": audio.size_bytes,
                            "created_at": audio.created_at
                        }
                        console_logger.debug(f"Added preferred audio URL for voice line {voice_line.id}")
                except Exception as e:
                    console_logger.warning(f"Failed to generate signed URL for voice line {voice_line.id}: {str(e)}")
            
            scenario_dict["voice_lines"].append(voice_line_dict)
        
        return ScenarioResponse.model_validate(scenario_dict)
    
    
    async def get_user_scenarios(self, user: AuthUser, limit: int = 50, offset: int = 0) -> List[ScenarioResponse]:
        """Get scenarios for a user"""
        scenarios = await self.repository.get_user_scenarios(user.id, limit, offset)
        return [ScenarioResponse.model_validate(scenario) for scenario in scenarios]


    async def enhance_voice_lines_with_feedback(self, user: AuthUser, voice_line_ids: List[int], 
                                              user_feedback: str) -> dict:
        """Enhance multiple voice lines with the same feedback, processing them one by one"""
        try:
            console_logger.info(f"Enhancing {len(voice_line_ids)} voice lines for user {user.id}")
            
            if not voice_line_ids:
                raise ValueError("No voice line IDs provided")
            
            # First, get all voice lines and their scenarios with RLS protection
            from sqlalchemy import select
            from app.models.voice_line import VoiceLine
            from app.models.scenario import Scenario
            
            query = (
                select(VoiceLine, Scenario)
                .join(Scenario)
                .where(VoiceLine.id.in_(voice_line_ids))
                .where(Scenario.user_id == user.id)  # RLS protection
            )
            
            result = await self.repository.db_session.execute(query)
            voice_lines_and_scenarios = result.all()
            
            if len(voice_lines_and_scenarios) != len(voice_line_ids):
                found_ids = [vl.id for vl, _ in voice_lines_and_scenarios]
                missing_ids = [vid for vid in voice_line_ids if vid not in found_ids]
                raise ValueError(f"Voice lines not found or access denied: {missing_ids}")
            
            # Process enhancement results
            successful_enhancements = []
            failed_enhancements = []
            
            # Import processor once
            from app.langchain.scenarios.enhancement_processor import IndividualVoiceLineEnhancementProcessor
            processor = IndividualVoiceLineEnhancementProcessor()
            
            # Process each voice line one by one
            for voice_line, scenario in voice_lines_and_scenarios:
                try:
                    console_logger.info(f"Processing voice line {voice_line.id}")
                    
                    # Create scenario data for the processor
                    from app.schemas.scenario import ScenarioCreateRequest
                    scenario_data = ScenarioCreateRequest(
                        title=scenario.title,
                        description=scenario.description,
                        target_name=scenario.target_name,
                        language=scenario.language
                    )
                    
                    # Process enhancement with LangChain
                    enhancement_result = await processor.process_voice_line_enhancement(
                        voice_line_id=voice_line.id,
                        original_text=voice_line.text,
                        user_feedback=user_feedback,
                        scenario_data=scenario_data,
                        voice_line_type=voice_line.type
                    )
                    
                    # Check if enhancement was successful and safe
                    if (enhancement_result['processing_complete'] and 
                        enhancement_result['safety_passed'] and 
                        enhancement_result['enhanced_text'] and
                        enhancement_result['enhanced_text'] != voice_line.text):
                        
                        # Store original text before update
                        original_text = voice_line.text
                        
                        # Update the voice line in database
                        updated_voice_line = await self.repository.update_voice_line_text(
                            voice_line.id, enhancement_result['enhanced_text'], user.id
                        )
                        
                        if updated_voice_line:
                            successful_enhancements.append({
                                "voice_line_id": voice_line.id,
                                "original_text": original_text,  # Use stored original text
                                "enhanced_text": enhancement_result['enhanced_text'],
                                "safety_passed": enhancement_result.get('safety_passed', False),
                                "safety_issues": enhancement_result.get('safety_issues', [])
                            })
                            console_logger.info(f"Successfully enhanced voice line {voice_line.id}")
                        else:
                            failed_enhancements.append({
                                "voice_line_id": voice_line.id,
                                "original_text": voice_line.text,
                                "error": "Failed to update voice line in database",
                                "safety_passed": enhancement_result.get('safety_passed', False),
                                "safety_issues": enhancement_result.get('safety_issues', [])
                            })
                    else:
                        # Enhancement failed or was unsafe or no change
                        reason = "No change needed"
                        if not enhancement_result.get('processing_complete', False):
                            reason = "Processing incomplete"
                        elif not enhancement_result.get('safety_passed', False):
                            reason = "Failed safety check"
                        elif not enhancement_result.get('enhanced_text'):
                            reason = "No enhanced text generated"
                        
                        failed_enhancements.append({
                            "voice_line_id": voice_line.id,
                            "original_text": voice_line.text,
                            "enhanced_text": enhancement_result.get('enhanced_text', ''),
                            "error": reason,
                            "safety_passed": enhancement_result.get('safety_passed', False),
                            "safety_issues": enhancement_result.get('safety_issues', [])
                        })
                        
                except Exception as e:
                    console_logger.error(f"Failed to enhance voice line {voice_line.id}: {str(e)}")
                    failed_enhancements.append({
                        "voice_line_id": voice_line.id,
                        "original_text": voice_line.text,
                        "error": f"Enhancement failed: {str(e)}",
                        "safety_passed": False,
                        "safety_issues": []
                    })
            
            # Commit all successful changes
            if successful_enhancements:
                await self.repository.commit()
                console_logger.info(f"Committed {len(successful_enhancements)} voice line enhancements")
            else:
                await self.repository.rollback()
                console_logger.info("No successful enhancements to commit")
            
            return {
                "success": len(successful_enhancements) > 0,
                "total_processed": len(voice_line_ids),
                "successful_count": len(successful_enhancements),
                "failed_count": len(failed_enhancements),
                "successful_enhancements": successful_enhancements,
                "failed_enhancements": failed_enhancements,
                "user_feedback": user_feedback
            }
                
        except Exception as e:
            console_logger.error(f"Bulk voice line enhancement failed: {str(e)}")
            await self.repository.rollback()
            raise

    async def set_preferred_voice(self, user: AuthUser, scenario_id: int, preferred_voice_id: str) -> ScenarioResponse:
        """Set or change scenario's preferred voice id"""
        updated = await self.repository.update_scenario_preferred_voice(scenario_id, user.id, preferred_voice_id)
        if not updated:
            raise ValueError("Scenario not found or access denied")
        await self.repository.commit()
        return ScenarioResponse.model_validate(updated)



