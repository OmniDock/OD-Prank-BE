"""
Design Chat Processor - Interactive scenario design assistant
"""
from langgraph.graph import StateGraph, START, END
from app.langchain.state import DesignChatState
from app.langchain.nodes.design_chat import (
    refine_description_node,
    generate_suggestion_node
)
from app.core.logging import console_logger


class DesignChatProcessor:
    """
    Interactive chat processor for scenario design.
    Helps users iteratively refine their prank ideas.
    """
    
    def __init__(self):
        """Initialize the processor and build the graph"""
        self.workflow = self._build_graph()
        console_logger.info("DesignChatProcessor initialized")
    
    def _build_graph(self) -> StateGraph:
        """
        Build the design chat graph
        
        Flow: Refine → Suggest → End (user decides when to finalize)
        """
        console_logger.info("Building design chat graph")
        
        # Create the graph
        graph = StateGraph(DesignChatState)
        
        # Add nodes
        graph.add_node("refine", refine_description_node)
        graph.add_node("suggest", generate_suggestion_node)
        
        # Simple linear flow
        graph.add_edge(START, "refine")
        graph.add_edge("refine", "suggest")
        graph.add_edge("suggest", END)
        
        return graph.compile()
    
    async def process(self, state: DesignChatState) -> DesignChatState:
        """
        Process one iteration of the design chat
        
        Args:
            state: Current chat state with messages and description
            
        Returns:
            Updated state with refined description and next suggestion
        """
        console_logger.info(f"Processing design chat with {len(state.messages)} messages")
        
        try:
            # Run the graph
            result = await self.workflow.ainvoke(state.model_dump())
            console_logger.info(f"Design chat processing result: {result}")

            # Convert result to DesignChatState
            if isinstance(result, dict):
                # Merge with existing state to preserve fields
                for key, value in result.items():
                    if value is not None:
                        setattr(state, key, value)
                return state
            
            
            return result
            
        except Exception as e:
            console_logger.error(f"Design chat processing failed: {str(e)}")
            state.next_suggestion = "Entschuldigung, es gab einen Fehler. Bitte versuche es nochmal oder beschreibe deine Idee anders."
            return state
    
    async def stream(self, state: DesignChatState):
        """
        Stream the processing for real-time updates (future enhancement)
        """
        async for event in self.workflow.astream(state.model_dump()):
            yield event
