from langgraph.graph import StateGraph, END, START
from app.core.logging import console_logger
from app.langchain.nodes.voice_line_enhancer import  VoiceLineEnhancer
from app.langchain.nodes.scenario_safety import ScenarioSafetyChecker
from app.langchain.nodes.scenario_analyzer import ScenarioAnalyzer
from .state import IndividualVoiceLineEnhancementState


class IndividualVoiceLineEnhancementProcessor:
    """Minimal LangGraph processor for individual voice line enhancement with user feedback"""

    def __init__(self):
        self.enhancer = VoiceLineEnhancer()
        self.safety_checker = ScenarioSafetyChecker()
        self.scenario_analyzer = ScenarioAnalyzer()
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Build the minimal LangGraph workflow"""
        console_logger.info("Building individual voice line enhancement workflow")
        
        workflow = StateGraph(IndividualVoiceLineEnhancementState)
        
        # Add nodes
        workflow.add_node("enhance_voice_line", self._enhance_voice_line_node)
        workflow.add_node("safety_check", self._safety_check_node)
        
        # Define flow
        workflow.add_edge(START, "enhance_voice_line")
        workflow.add_conditional_edges(
            "enhance_voice_line",
            self._safety_router,
            {
                "safety_check": "safety_check",
                "complete": END
            }
        )
        workflow.add_edge("safety_check", END)
        
        return workflow.compile()

    async def process_voice_line_enhancement(self, voice_line_id: int, original_text: str, 
                                           user_feedback: str, scenario_data, voice_line_type, 
                                           scenario_analysis=None) -> IndividualVoiceLineEnhancementState:
        """Process individual voice line enhancement - public method"""
        state = IndividualVoiceLineEnhancementState(
            voice_line_id=voice_line_id,
            original_text=original_text,
            user_feedback=user_feedback,
            scenario_data=scenario_data,
            voice_line_type=voice_line_type,
            scenario_analysis=scenario_analysis
        )
        
        result = await self.workflow.ainvoke(state)
        return result

    async def _enhance_voice_line_node(self, state: IndividualVoiceLineEnhancementState) -> IndividualVoiceLineEnhancementState:
        """Enhance the voice line based on user feedback"""
        try:
            console_logger.info(f"Enhancing voice line {state.voice_line_id} with feedback")
            
            # Use the existing enhancer but adapt for individual enhancement
            result = await self._enhance_single_voice_line(
                state.scenario_data,
                state.voice_line_type,
                state.original_text,
                state.user_feedback
            )
            
            return {
                "enhanced_text": result,
                "enhancement_attempt": state.enhancement_attempt + 1
            }
        except Exception as e:
            console_logger.error(f"Voice line enhancement failed: {str(e)}")
            return {
                "enhanced_text": state.original_text,  # Fallback to original
                "enhancement_attempt": state.enhancement_attempt + 1
            }

    async def _enhance_single_voice_line(self, scenario_data, voice_line_type, original_text, user_feedback):
        """Enhanced voice line generation with feedback"""
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
        from pydantic import BaseModel, Field
        
        class EnhancementResult(BaseModel):
            enhanced_text: str = Field(description="Enhanced voice line based on feedback")
        
        llm = ChatOpenAI(model="gpt-4.1", temperature=0.6).with_structured_output(EnhancementResult)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert prank call script writer. Enhance voice lines based on user feedback.
            
            Make the voice line:
            - Natural and conversational
            - Optimized for ElevenLabs TTS (use [laughter], [pause], etc.)
            - Safe and respectful
            - Addressing the specific feedback provided
            """),
            ("user", """
            Scenario: {title} - {description}
            Target: {target_name}
            Language: {language}
            Type: {voice_line_type}
            
            Original: {original_text}
            Feedback: {user_feedback}
            
            Enhance this voice line based on the feedback.
            """)
        ])
        
        chain = prompt | llm
        result = await chain.ainvoke({
            "title": scenario_data.title,
            "description": scenario_data.description,
            "target_name": scenario_data.target_name,
            "language": scenario_data.language,
            "voice_line_type": voice_line_type if isinstance(voice_line_type, str) else voice_line_type.value,
            "original_text": original_text,
            "user_feedback": user_feedback
        })
        
        return result.enhanced_text

    async def _safety_check_node(self, state: IndividualVoiceLineEnhancementState) -> IndividualVoiceLineEnhancementState:
        """Check safety of enhanced voice line"""
        try:
            console_logger.info(f"Checking safety of enhanced voice line {state.voice_line_id}")
            
            # Create a simple voice line state for safety check
            from app.langchain.scenarios.state import VoiceLineState
            voice_line_for_safety = VoiceLineState(
                text=state.enhanced_text,
                type=state.voice_line_type
            )
            
            # Use the overall safety check method
            result = await self.safety_checker.check_overall_safety(
                state.scenario_data,
                [voice_line_for_safety],
                state.scenario_analysis
            )
            
            return {
                "safety_passed": result.is_safe,
                "safety_issues": result.issues,
                "processing_complete": True
            }
        except Exception as e:
            console_logger.error(f"Safety check failed: {str(e)}")
            return {
                "safety_passed": False,
                "safety_issues": [f"Safety check failed: {str(e)}"],
                "processing_complete": True
            }

    async def _safety_router(self, state: IndividualVoiceLineEnhancementState) -> str:
        """Route based on enhancement completion"""
        if state.enhanced_text and state.enhanced_text != state.original_text:
            return "safety_check"
        else:
            return "complete"