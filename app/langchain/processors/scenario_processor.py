"""
Main processor for LangChain v2 scenario generation
"""
from typing import Optional, List
from langgraph.graph import StateGraph, START, END
from app.langchain.state import ScenarioState
from app.langchain.nodes.extractor import extractor_node
# from app.langchain.nodes.clarifier import clarifier_node
from app.langchain.nodes.analyzer import analyzer_node
from app.langchain.nodes.generator import generator_node
from app.langchain.nodes.tts_refiner import tts_refiner_node
from app.langchain.nodes.judge import judge_node
from app.langchain.nodes.rewriter import rewriter_node
from app.langchain.nodes.safety import safety_node

from app.langchain.nodes.enhancer import enhancer_node
from app.core.logging import console_logger


class ScenarioProcessor:
    """
    Main processor for scenario generation with quality control
    """
    
    def __init__(self):
        """Initialize the processor and build the graph"""
        self.workflow = self._build_graph()
        console_logger.info("ScenarioProcessor initialized")
    
    def _build_graph(self) -> StateGraph:
        """
        Build the processing graph with conditional routing
        """
        console_logger.info("Building LangChain v2 graph")
        
        # Create the graph
        graph = StateGraph(ScenarioState)
        
        # Add all nodes
        graph.add_node("extractor", extractor_node)
        graph.add_node("analyzer", analyzer_node)
        graph.add_node("generator", generator_node)
        graph.add_node("tts_refiner", tts_refiner_node)
        graph.add_node("judge", judge_node)
        graph.add_node("rewriter", rewriter_node)
        graph.add_node("safety", safety_node)
        
        # Define the flow
        graph.add_edge(START, "extractor")
        
        # Conditional routing after clarifier
        def route_after_clarifier(state: ScenarioState) -> str:
            """Route based on clarification needs"""
            if state.require_clarification and state.clarifying_questions:
                console_logger.info("Clarification needed - ending early")
                return "end"
            console_logger.info("No clarification needed - continuing")
            return "analyzer"
        
        graph.add_conditional_edges(
            "extractor",
            route_after_clarifier,
            {
                "analyzer": "analyzer",
                "end": END
            }
        )
        
        # Linear flow from analyzer to judge
        graph.add_edge("analyzer", "generator")
        graph.add_edge("generator", "tts_refiner")
        graph.add_edge("tts_refiner", "judge")
        
        # Conditional routing after judge
        def route_after_judge(state: ScenarioState) -> str:
            """Route based on quality scores"""
            if state.quality:
                # Rewrite if seriousness OR believability is too low
                if state.quality.seriousness < 0.7 or state.quality.believability < 0.6:
                    console_logger.info(
                        f"Quality too low (S:{state.quality.seriousness:.2f}, "
                        f"B:{state.quality.believability:.2f}) - rewriting"
                    )
                    return "rewriter"
            console_logger.info("Quality acceptable - proceeding to safety")
            return "safety"
        
        graph.add_conditional_edges(
            "judge",
            route_after_judge,
            {
                "rewriter": "rewriter",
                "safety": "safety"
            }
        )
        
        # Rewriter always goes to safety (no loop!)
        graph.add_edge("rewriter", "safety")
        
        # Safety is the final node
        graph.add_edge("safety", END)
        
        # Compile the graph
        compiled = graph.compile()
        console_logger.info("Graph compiled successfully")
        
        return compiled
    
    async def process(self, state: ScenarioState) -> ScenarioState:
        """
        Process a scenario through the pipeline
        
        Args:
            state: Initial state with scenario data
            
        Returns:
            Processed state with generated content or clarifying questions
        """
        console_logger.info(f"Processing scenario: {state.scenario_data.title}")
        try:
            # Run the workflow
            result = await self.workflow.ainvoke(state)
            
            # Log completion status
            if result.get("processing_complete"):
                console_logger.info("Processing completed successfully")
            elif result.get("clarifying_questions"):
                console_logger.info(f"Clarification needed: {len(result['clarifying_questions'])} questions")
            else:
                console_logger.warning("Processing ended without completion")
            
            return result
            
        except Exception as e:
            console_logger.error(f"Processing failed: {str(e)}")
            raise
    
    async def process_with_clarifications(
        self, 
        state: ScenarioState, 
        clarifying_questions: Optional[List[str]] = None,
        clarifications: Optional[dict] = None
    ) -> ScenarioState:
        """
        Process with optional clarifications
        
        Args:
            state: Initial state
            clarifications: Optional clarification answers
            
        Returns:
            Processed state
        """
        if clarifications:
            state.clarifying_questions = clarifying_questions
            state.clarifications = clarifications
            state.require_clarification = False
            console_logger.info("Processing with clarifications provided")
        
        return await self.process(state)
