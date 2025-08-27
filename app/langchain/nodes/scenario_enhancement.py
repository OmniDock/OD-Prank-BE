from langchain_openai import ChatOpenAI
from app.schemas.scenario import ScenarioCreateRequest
from app.langchain.scenarios.state import ScenarioEnhancementState


class ScenarioEnhancer:
    def __init__(self, model_name: str = "gpt-4.1"):
        self.model_name = model_name
        self.llm = ChatOpenAI(model=self.model_name, temperature=0.6).with_structured_output(ScenarioEnhancementState)

    async def enhance_scenario(self, scenario_data: ScenarioEnhancementState) -> ScenarioEnhancementState:
        pass