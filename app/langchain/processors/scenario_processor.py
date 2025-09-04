"""
Main processor for LangChain v2 scenario generation
"""
from langgraph.graph import StateGraph, START, END
from app.langchain.state import ScenarioState
from app.langchain.nodes.extractor import extractor_node
from app.langchain.nodes.analyzer import analyzer_node
from app.langchain.nodes.generator import generator_node
from app.langchain.nodes.tts_refiner import tts_refiner_node
from app.langchain.nodes.safety import safety_node

from app.core.logging import console_logger


class ScenarioProcessor:
    """
    Main processor for scenario generation with quality control
    """
    
    def __init__(self):
        """Initialize the processor and build the graph"""
        self.workflow = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """
        Build the processing graph with conditional routing
        """
        console_logger.debug("Building LangChain v2 graph")

        # Create the graph
        graph = StateGraph(ScenarioState)
        
        # Add all nodes
        graph.add_node("extractor", extractor_node)
        graph.add_node("analyzer", analyzer_node)
        graph.add_node("generator", generator_node)
        graph.add_node("tts_refiner", tts_refiner_node)
        graph.add_node("safety", safety_node)
        
        # Define the flow
        graph.add_edge(START, "extractor")
        graph.add_edge("extractor", "analyzer")
        
        # Linear flow from analyzer to judge
        graph.add_edge("analyzer", "generator")
        graph.add_edge("generator", "tts_refiner")
        graph.add_edge("tts_refiner", "safety")
        
        # Safety is the final node
        graph.add_edge("safety", END)
        
        # Compile the graph
        compiled = graph.compile()
        console_logger.debug("Graph compiled successfully")
        
        return compiled
    
    async def process(self, state: ScenarioState) -> ScenarioState:
        """
        Process a scenario through the pipeline
        
        Args:
            state: Initial state with scenario data
            
        Returns:
            Processed state with generated content or clarifying questions
        """
        try:
            # Run the workflow
            result = await self.workflow.ainvoke(state)
            
            # Log completion status
            if result.get("processing_complete"):
                console_logger.debug("Processing completed successfully")
            else:
                console_logger.warning("Processing ended without completion")
            
            return result
            
        except Exception as e:
            console_logger.error(f"Processing failed: {str(e)}")
            raise
    