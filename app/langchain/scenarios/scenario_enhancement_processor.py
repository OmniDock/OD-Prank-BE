from app.core.logging import console_logger
from langgraph.graph import StateGraph, END, START
from app.langchain.nodes.scenario_safety import ScenarioSafetyChecker
from app.langchain.scenarios.state import ScenarioEnhancementState, SafetyCheckResult
from app.langchain.nodes.scenario_follow_up import ScenarioFollowUp
from app.schemas.scenario import ScenarioEnhancementRequest
from app.langchain.nodes.scenario_enhancement import ScenarioEnhancer
class ScenarioQuestionProcessor():

    def __init__(self) -> None:
        self.scenario_safety = ScenarioSafetyChecker()
        self.scenario_enhancer = None
        self.workflow = self._build_workflow()

    def _build_workflow(self):
        console_logger.info("Building Enhancement workflow")
        """Build the LangGraph workflow"""
        workflow = StateGraph(ScenarioEnhancementState)

        workflow.add_node("initial_safety", self._initial_safety_node)
        workflow.add_node("scenario_enhancement", self._scenario_enhancement_node)

        workflow.add_edge(START, "initial_safety")
        workflow.add_edge("initial_safety", "scenario_enhancement")
        workflow.add_edge("scenario_enhancement", END)

        return workflow
    
    async def process_enhancement(self, scenario_data: ScenarioEnhancementRequest) -> ScenarioEnhancementState:
        state = ScenarioEnhancementState(scenario_data=scenario_data)

        result = await self.workflow.ainvoke(state)
        return result
    
