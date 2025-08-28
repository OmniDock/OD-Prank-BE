from app.core.logging import console_logger
from langgraph.graph import StateGraph, END, START
from app.langchain.nodes.scenario_safety import ScenarioSafetyChecker
from app.langchain.scenarios.state import ScenarioEnhancementState, SafetyCheckResult
from app.langchain.nodes.scenario_follow_up import ScenarioFollowUp
from app.schemas.scenario import ScenarioEnhancementRequest
from app.langchain.nodes.scenario_enhancement import ScenarioEnhancer

class ScenarioEnhancementProcessor():

    def __init__(self) -> None:
        self.scenario_safety = ScenarioSafetyChecker()
        self.scenario_enhancer = ScenarioEnhancer()
        self.workflow = self._build_workflow()

    def _build_workflow(self):
        console_logger.info("Building Enhancement workflow")
        """Build the LangGraph workflow"""
        workflow = StateGraph(ScenarioEnhancementState)

        workflow.add_node("scenario_enhancement", self._scenario_enhancement_node)

        workflow.add_edge(START, "scenario_enhancement")
        workflow.add_edge("scenario_enhancement", END)

        return workflow.compile()
    
    async def process_enhancement(self, scenario_data: ScenarioEnhancementRequest) -> ScenarioEnhancementState:
        state = ScenarioEnhancementState(
            scenario_data=scenario_data.original_request,
            follow_up_questions=scenario_data.questions,
            answers=scenario_data.answers
        )

        result = await self.workflow.ainvoke(state)
        return result
        
    async def _scenario_enhancement_node(self, state: ScenarioEnhancementState) -> ScenarioEnhancementState:
        """Enhance scenario with user answers"""
        try:
            result = await self.scenario_enhancer.enhance_scenario(state)
            return result
        except Exception as e:
            console_logger.error(f"Scenario enhancement failed: {str(e)}")
            return state
    
