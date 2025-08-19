from app.langchain.scenarios.initial_processor import InitialScenarioProcessor
from app.langchain.scenarios.state import ScenarioProcessorState, VoiceLineState
from app.schemas.scenario import ScenarioCreateRequest, ScenarioCreateResponse, ScenarioResponse
from app.core.auth import AuthUser
from app.repositories.scenario_repository import ScenarioRepository
from app.core.database import AsyncSession
from app.core.logging import console_logger
from typing import List
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
            

            console_logger.info(results)
            
            # Step 2: Determine safety status from results
            is_safe = results['overall_safety_passed']
            safety_issues = "; ".join(results['overall_safety_issues']) if results['overall_safety_issues'] else None
            
            # Step 3: Create scenario in database
            scenario_db_data = {
                "user_id": user.id,
                "title": scenario_data.title,
                "description": scenario_data.description,
                "language": scenario_data.language,
                "target_name": scenario_data.target_name,
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
                "initial_safety_passed": results['initial_safety_passed'],
                "initial_safety_attempts": results['initial_safety_attempts'],
                "overall_safety_passed": results['overall_safety_passed'],
                "overall_diversity_passed": results['overall_diversity_passed'],
                "processing_complete": results['processing_complete'],
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
                "storage_url": None  
            })
        
        for voice_line_state in results['question_voice_lines']:
            voice_lines_data.append({
                "text": voice_line_state.text,
                "type": voice_line_state.type.value,
                "storage_url": None
            })
        
        for voice_line_state in results['response_voice_lines']:
            voice_lines_data.append({
                "text": voice_line_state.text,
                "type": voice_line_state.type.value,
                "storage_url": None
            })
        
        for voice_line_state in results['closing_voice_lines']:
            voice_lines_data.append({
                "text": voice_line_state.text,
                "type": voice_line_state.type.value,
                "storage_url": None
            })
        
        console_logger.info(f"Extracted {len(voice_lines_data)} voice lines for database storage")
        return voice_lines_data
    
    
    async def get_scenario(self, user: AuthUser, scenario_id: int) -> ScenarioResponse:
        """Get a scenario by ID"""
        scenario = await self.repository.get_scenario_by_id(scenario_id, user.id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found or access denied")
        
        return ScenarioResponse.model_validate(scenario)
    
    
    async def get_user_scenarios(self, user: AuthUser, limit: int = 50, offset: int = 0) -> List[ScenarioResponse]:
        """Get scenarios for a user"""
        scenarios = await self.repository.get_user_scenarios(user.id, limit, offset)
        return [ScenarioResponse.model_validate(scenario) for scenario in scenarios]







