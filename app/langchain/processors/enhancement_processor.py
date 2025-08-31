"""
Enhancement processor for improving existing voice lines with user feedback
"""
from typing import Optional, List, Dict, Any
from langgraph.graph import StateGraph, START, END
from app.langchain.state import ScenarioState
from app.langchain.nodes.enhancer import enhancer_node, enhance_single_line
from app.langchain.nodes.tts_refiner import tts_refiner_node
from app.langchain.nodes.judge import judge_node
from app.langchain.nodes.safety import safety_node
from app.core.logging import console_logger


class EnhancementProcessor:
    """
    Processor for enhancing existing voice lines based on user feedback
    """
    
    def __init__(self):
        """Initialize the enhancement processor"""
        self.workflow = self._build_graph()
        console_logger.info("EnhancementProcessor initialized")
    
    def _build_graph(self) -> StateGraph:
        """
        Build the enhancement graph
        
        Flow: Enhance → TTS Refine → Judge → Safety
        """
        console_logger.info("Building enhancement graph")
        
        graph = StateGraph(ScenarioState)
        
        # Add nodes
        graph.add_node("enhance", enhancer_node)
        graph.add_node("tts_refine", tts_refiner_node)
        graph.add_node("judge", judge_node)
        graph.add_node("safety", safety_node)
        
        # Define flow
        graph.add_edge(START, "enhance")
        graph.add_edge("enhance", "tts_refine")
        graph.add_edge("tts_refine", "judge")
        graph.add_edge("judge", "safety")
        graph.add_edge("safety", END)
        
        return graph.compile()
    
    async def enhance_scenario(
        self,
        original_state: ScenarioState,
        user_feedback: str
    ) -> ScenarioState:
        """
        Enhance an entire scenario based on user feedback
        
        Args:
            original_state: The original ScenarioState with generated content
            user_feedback: User's improvement requests
            
        Returns:
            Enhanced ScenarioState
        """
        console_logger.info("Starting scenario enhancement")
        
        # Add feedback to state
        original_state.user_feedback = user_feedback
        
        # Run enhancement workflow
        result = await self.workflow.ainvoke(original_state)
        
        # Mark as enhanced
        if isinstance(result, dict):
            result['was_enhanced'] = True
        else:
            result.was_enhanced = True
        
        console_logger.info("Enhancement complete")
        return result
    
    async def enhance_voice_lines(
        self,
        voice_lines: Dict[str, List[str]],
        user_feedback: str,
        scenario_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, List[str]]:
        """
        Enhance specific voice lines without full workflow
        
        Args:
            voice_lines: Dict of voice type to lines
            user_feedback: User's improvement requests
            scenario_analysis: Optional analysis data for context
            
        Returns:
            Enhanced voice lines
        """
        enhanced = {}
        
        persona_name = "Agent"
        company_service = "Service"
        
        if scenario_analysis and "analysis" in scenario_analysis:
            analysis = scenario_analysis["analysis"]
            persona_name = analysis.get("persona_name", persona_name)
            company_service = analysis.get("company_service", company_service)
        
        for voice_type, lines in voice_lines.items():
            enhanced[voice_type] = []
            for line in lines:
                enhanced_line = await enhance_single_line(
                    line_text=line,
                    line_type=voice_type,
                    user_feedback=user_feedback,
                    persona_name=persona_name,
                    company_service=company_service
                )
                enhanced[voice_type].append(enhanced_line)
        
        return enhanced


class SingleLineEnhancer:
    """
    Utility for enhancing individual voice lines
    """
    
    @staticmethod
    async def enhance(
        voice_line_id: int,
        original_text: str,
        voice_line_type: str,
        user_feedback: str,
        scenario_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Enhance a single voice line
        
        Returns:
            Dict with enhanced_text, is_safe, changes_made
        """
        console_logger.info(f"Enhancing voice line {voice_line_id}")
        
        # Extract context from analysis
        persona_name = "Agent"
        company_service = "Service"
        language = "de"
        
        if scenario_analysis:
            if "analysis" in scenario_analysis:
                analysis = scenario_analysis["analysis"]
                persona_name = analysis.get("persona_name", persona_name)
                company_service = analysis.get("company_service", company_service)
            if "language" in scenario_analysis:
                language = scenario_analysis.get("language", language)
        
        # Enhance the line
        enhanced_text = await enhance_single_line(
            line_text=original_text,
            line_type=voice_line_type,
            user_feedback=user_feedback,
            persona_name=persona_name,
            company_service=company_service,
            language=language
        )
        
        # Quick safety check
        is_safe = not any(
            danger in enhanced_text.lower() 
            for danger in ["password", "credit card", "bank account", "social security"]
        )
        
        return {
            "voice_line_id": voice_line_id,
            "original_text": original_text,
            "enhanced_text": enhanced_text,
            "is_safe": is_safe,
            "changes_made": ["Applied user feedback", "Maintained character consistency"]
        }
