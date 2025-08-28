from typing import Dict
from langgraph.graph import StateGraph, END, START
from app.core.logging import console_logger

# Inputs
from app.core.utils.enums import VoiceLineTypeEnum
from app.schemas.scenario import ScenarioCreateRequest

# Nodes 
from app.langchain.nodes.scenario_safety import ScenarioSafetyChecker
from app.langchain.nodes.voice_line_generator import VoiceLineGenerator
from app.langchain.nodes.scenario_analyzer import ScenarioAnalyzer, ScenarioAnalysisResult
from app.langchain.nodes.scenario_enhancer import ScenarioEnhancer

# State
from .state import ScenarioProcessorState,ScenarioProccessorStateV2, VoiceLineState, SafetyCheckResult


class InitialScenarioProcessor: 

    def __init__(self, target_counts: Dict[VoiceLineTypeEnum, int]):
        self.target_counts = target_counts
        # Node Classes 
        self.scenario_safety = ScenarioSafetyChecker()
        self.scenario_enhancer = ScenarioEnhancer()
        self.scenario_analyzer = ScenarioAnalyzer()
        self.voice_line_generator = VoiceLineGenerator()
        self.workflow = self._build_workflow()
    
    @classmethod
    def with_default_counts(cls) -> "InitialScenarioProcessor":
        """Create processor with default target counts for each voice line type"""
        default_counts = {
            VoiceLineTypeEnum.OPENING: 3,
            VoiceLineTypeEnum.QUESTION: 5,
            VoiceLineTypeEnum.RESPONSE: 5,
            VoiceLineTypeEnum.CLOSING: 3
        }
        return cls(default_counts)


    def _build_workflow(self) -> StateGraph:
        console_logger.info("Building workflow")
        """Build the LangGraph workflow"""
        workflow = StateGraph(ScenarioProccessorStateV2)
        
        #nodes
        workflow.add_node("answer_safety", self._answer_safety_node)
        workflow.add_node("enhance_scenario", self._enhance_scenario_node)

        workflow.add_node("voice_line_generation_parallel_node", self._voice_line_generation_parallel_node)

        workflow.add_node("generate_opening", self._generate_opening_node)
        workflow.add_node("generate_question", self._generate_question_node)
        workflow.add_node("generate_response", self._generate_response_node)
        workflow.add_node("generate_closing", self._generate_closing_node)

        workflow.add_node("collect_results", self._collect_results_node)
        workflow.add_node("overall_safety_check", self._overall_safety_check_node)


        #edges 
        workflow.add_edge(START, "answer_safety")

        workflow.add_conditional_edges(
            "answer_safety",
            self._answer_safety_router,
            {
                "continue": "enhance_scenario",
                "end": END
            }
        )

        # Scenario analysis flows to voice line generation
        workflow.add_edge("enhance", "voice_line_generation_parallel_node")

        workflow.add_edge("voice_line_generation_parallel_node", "generate_opening")
        workflow.add_edge("voice_line_generation_parallel_node", "generate_question")
        workflow.add_edge("voice_line_generation_parallel_node", "generate_response")
        workflow.add_edge("voice_line_generation_parallel_node", "generate_closing")
        
        # All generation nodes go to END (they run in parallel)
        workflow.add_edge("generate_opening", "collect_results")
        workflow.add_edge("generate_question", "collect_results")
        workflow.add_edge("generate_response", "collect_results")
        workflow.add_edge("generate_closing", "collect_results")

        workflow.add_edge("collect_results", "overall_safety_check")
        workflow.add_edge("overall_safety_check", END)

        return workflow.compile()
    

        
    async def _answer_safety_node(self, state: ScenarioProccessorStateV2) -> ScenarioProccessorStateV2:
        """Initial scenario safety check"""
        try:
            result = await self.scenario_safety.check_answer_safety(
                scenario_description=state.start_scenario_data.description,
                questions=state.questions, 
                answers=state.answers)
            return {
                "answers_safety_check": result
            }
        except Exception as e:
            return {
                "answers_safety_check": SafetyCheckResult(
                    is_safe=False,
                    confidence=0.0,
                    severity="critical",
                    issues=[f"Safety check failed: {str(e)}"],
                    categories=[],
                    recommendation="reject",
                    reasoning=f"Safety check failed: {str(e)}"
                )
            }
        
    async def _enhance_scenario_node(self, state: ScenarioProccessorStateV2) -> ScenarioProccessorStateV2:
        """Enhance the scenario"""
        try:
            enhanced_description = await self.scenario_enhancer.enhance_scenario(
                questions=state.questions,
                answers=state.answers,
                scenario_description=state.start_scenario_data.description
            )
            return {
                "enhanced_scenario_description": enhanced_description
            }
        except Exception as e:
            console_logger.error(f"Scenario enhancement failed: {str(e)}")
            return {
                "enhanced_scenario_description": state.start_scenario_data.description
            }
        
    async def _answer_safety_router(self, state: ScenarioProccessorStateV2) -> str:
        """Route based on answer safety assessment"""
        if state.answers_safety_check.is_safe:
            console_logger.info("Answer safety check passed, proceeding with scenario enhancement")
            return "continue"
        else:
            console_logger.warning(f"Answer safety check failed: {state.answers_safety_check.issues}")
            return "end"
        
    async def _voice_line_generation_parallel_node(self, state: ScenarioProccessorStateV2) -> str:
        """Route based on voice line generation"""
        return state
    
    async def _generate_opening_node(self, state: ScenarioProccessorStateV2) -> ScenarioProccessorStateV2:
        """Generate opening voice lines"""
        try:
            count = state.target_counts.get(VoiceLineTypeEnum.OPENING.value)
            result = await self.voice_line_generator.generate_opening_voice_lines(
                title=state.start_scenario_data.title,
                description=state.enhanced_scenario_description, 
                target_name=state.start_scenario_data.target_name,
                language=state.start_scenario_data.language,
                count=count
            )
            
            # Convert to VoiceLineState objects - return them, don't append
            new_voice_lines = []
            for text in result.voice_lines:
                voice_line = VoiceLineState(
                    text=text,
                    type=VoiceLineTypeEnum.OPENING,
                )
                new_voice_lines.append(voice_line)
            
            # Return partial state update - LangGraph will merge using the reducer
            return {
                "opening_voice_lines": new_voice_lines,
                #"opening_generation_attempts": state.opening_generation_attempts + 1
            }
            
        except Exception as e:
            console_logger.error(f"Opening voice line generation failed: {str(e)}")
            return {
                #"opening_generation_attempts": state.opening_generation_attempts + 1
            }
        
    async def _generate_question_node(self, state: ScenarioProccessorStateV2) -> ScenarioProccessorStateV2:
        """Generate question voice lines"""
        try:
            count = state.target_counts.get(VoiceLineTypeEnum.QUESTION.value)
            result = await self.voice_line_generator.generate_question_voice_lines(
                title=state.start_scenario_data.title,
                description=state.enhanced_scenario_description, 
                target_name=state.start_scenario_data.target_name,
                language=state.start_scenario_data.language,
                count=count
            )
            
            # Convert to VoiceLineState objects - return them, don't append
            new_voice_lines = []
            for text in result.voice_lines:
                voice_line = VoiceLineState(
                    text=text,
                    type=VoiceLineTypeEnum.QUESTION,
                )
                new_voice_lines.append(voice_line)
            
            # Return partial state update - LangGraph will merge using the reducer
            return {
                "question_voice_lines": new_voice_lines,
                #"question_generation_attempts": state.question_generation_attempts + 1
            }
        except Exception as e:
            console_logger.error(f"Question voice line generation failed: {str(e)}")
            return {
                #"question_generation_attempts": state.question_generation_attempts + 1
            }
        
    async def _generate_response_node(self, state: ScenarioProccessorStateV2) -> ScenarioProccessorStateV2:
        """Generate response voice lines"""
        try:
            count = state.target_counts.get(VoiceLineTypeEnum.RESPONSE.value)
            result = await self.voice_line_generator.generate_response_voice_lines(
                title=state.start_scenario_data.title,
                description=state.enhanced_scenario_description, 
                target_name=state.start_scenario_data.target_name,
                language=state.start_scenario_data.language,
                count=count
            )
            
            
            # Convert to VoiceLineState objects - return them, don't append
            new_voice_lines = []
            for text in result.voice_lines:
                voice_line = VoiceLineState(
                    text=text,
                    type=VoiceLineTypeEnum.RESPONSE,
                )
                new_voice_lines.append(voice_line)
            
            # Return partial state update - LangGraph will merge using the reducer
            return {
                "response_voice_lines": new_voice_lines,
                #"response_generation_attempts": state.response_generation_attempts + 1
            }
        except Exception as e:
            console_logger.error(f"Response voice line generation failed: {str(e)}")
            return {
                #"response_generation_attempts": state.response_generation_attempts + 1
            }

    async def _generate_closing_node(self, state: ScenarioProccessorStateV2) -> ScenarioProccessorStateV2:
        """Generate closing voice lines"""
        try:
            count = state.target_counts.get(VoiceLineTypeEnum.CLOSING.value)
            result = await self.voice_line_generator.generate_closing_voice_lines(
                title=state.start_scenario_data.title,
                description=state.enhanced_scenario_description, 
                target_name=state.start_scenario_data.target_name,
                language=state.start_scenario_data.language,
                count=count
            )
            
            # Convert to VoiceLineState objects - return them, don't append
            new_voice_lines = []
            for text in result.voice_lines:
                voice_line = VoiceLineState(
                    text=text,
                    type=VoiceLineTypeEnum.CLOSING,
                )
                new_voice_lines.append(voice_line)
            
            # Return partial state update - LangGraph will merge using the reducer
            return {
                "closing_voice_lines": new_voice_lines,
                #"closing_generation_attempts": state.closing_generation_attempts + 1
            }
        except Exception as e:
            console_logger.error(f"Closing voice line generation failed: {str(e)}")
            return {
                #"closing_generation_attempts": state.closing_generation_attempts + 1
            }
    
    async def _collect_results_node(self, state: ScenarioProccessorStateV2) -> ScenarioProccessorStateV2:
        """Collect and finalize results from parallel voice line generation"""
        console_logger.info("Collecting voice line generation results")
        return {
            "processing_complete": True
        }
    
    async def _overall_safety_check_node(self, state: ScenarioProccessorStateV2) -> ScenarioProccessorStateV2:
        """Overall safety check"""
        try:
            result = await self.scenario_safety.check_overall_safety(
                state.enhanced_scenario_description,
                state.opening_voice_lines + state.question_voice_lines + state.response_voice_lines + state.closing_voice_lines,
            )
            # At the end, be slightly stricter: allow and modify pass, review passes with issues flagged
            return {
                "overall_safety_check": result
            }
        except Exception as e:
            return {
                "overall_safety_check": SafetyCheckResult(
                    is_safe=False,
                    confidence=0.0,
                    severity="critical",
                    issues=[f"Safety check failed: {str(e)}"],
                    categories=[],
                    recommendation="reject",
                    reasoning=f"Safety check failed: {str(e)}"
                )
            }
