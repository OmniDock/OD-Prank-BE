


from app.langchain.nodes.voice_line_enhancer import VoiceLineEnhancer
from app.core.logging import console_logger
from langgraph.graph import StateGraph
from .state import ScenarioProcessorState





class EnhancementScenarioProcessor: 

    def __init__(self):
        self.voice_line_enhancer = VoiceLineEnhancer()
        self.workflow = self._build_workflow()

    def _build_workflow(self):
        console_logger.info("Building workflow")

        workflow = StateGraph(ScenarioProcessorState)
        workflow.add_node("voice_line_enhancer", self._voice_line_enhancer_node)


        return workflow
    

    async def _voice_line_enhancer_node(self, state: ScenarioProcessorState) -> ScenarioProcessorState:
        console_logger.info("Enhancing voice lines")
        return state
    

    async def _voice_line_safety_node(self, state: ScenarioProcessorState) -> ScenarioProcessorState:
        console_logger.info("Checking voice line safety")
        return state
    

    async def _voice_line_safety_router(self, state: ScenarioProcessorState) -> str:
        console_logger.info("Routing voice line safety")
        return "voice_line_enhancer"
    