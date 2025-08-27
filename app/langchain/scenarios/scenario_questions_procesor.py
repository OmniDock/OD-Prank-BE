from app.core.logging import console_logger
from langgraph.graph import StateGraph, END, START
from app.langchain.nodes.scenario_safety import ScenarioSafetyChecker
from app.langchain.scenarios.state import ScenarioEnhancementState, SafetyCheckResult
from app.langchain.nodes.scenario_follow_up import ScenarioFollowUp
from app.schemas.scenario import ScenarioCreateRequest

class ScenarioQuestionProcessor():

    def __init__(self) -> None:
        self.scenario_safety = ScenarioSafetyChecker()
        self.scenario_follow_up = ScenarioFollowUp()
        self.workflow = self._build_workflow()

    def _build_workflow(self):
        console_logger.info("Building Enhancement workflow")
        """Build the LangGraph workflow"""
        workflow = StateGraph(ScenarioEnhancementState)

        workflow.add_node("initial_safety", self._initial_safety_node)
        workflow.add_node("follow_up_questions", self._follow_up_questions_node)

        workflow.add_edge(START, "initial_safety")        
        workflow.add_conditional_edges(
            "initial_safety",
            self._initial_safety_router,
            {
                "continue": "follow_up_questions",
                "end": END
            }
        )
        workflow.add_edge("follow_up_questions", "end")

    async def process_enhancement(self,scenario_create_request: ScenarioCreateRequest) -> ScenarioEnhancementState:
        state = ScenarioEnhancementState(
            scenario_data=scenario_create_request,
        )
        result = await self.workflow.ainvoke(state)
        return result
    

    ### Runnable Node Callers. 
    async def _initial_safety_node(self, state: ScenarioEnhancementState) -> ScenarioEnhancementState:
        """Initial scenario safety check"""
        try:
            result = await self.scenario_safety.check_initial_safety(state.scenario_data)
            return {
                "initial_safety_check": result
            }
        except Exception as e:
            return {
                "initial_safety_check": SafetyCheckResult(
                    is_safe=False,
                    confidence=0.0,
                    severity="critical",
                    issues=[f"Safety check failed: {str(e)}"],
                    categories=[],
                    recommendation="reject",
                    reasoning=f"Safety check failed: {str(e)}"
                )
            }

    async def _initial_safety_router(self, state: ScenarioEnhancementState) -> str:
        """Route based on safety assessment"""
        if state.initial_safety_check.is_safe:
            console_logger.info("Safety check passed, proceeding with scenario analysis")
            return "continue"
        else:
            console_logger.warning(f"Safety check failed: {state.initial_safety_check.issues}")
            return "end"
    
    
    async def _follow_up_questions_node(self, state: ScenarioEnhancementState) -> ScenarioEnhancementState:
        """Follow up questions"""
        try:
            result = await self.scenario_follow_up.generate_follow_up_quetsions(state.scenario_data)
            return {
                "follow_up_questions": result
            }
        except Exception as e:
            return {
                "follow_up_questions": f"Follow up questions failed: {str(e)}"
            }