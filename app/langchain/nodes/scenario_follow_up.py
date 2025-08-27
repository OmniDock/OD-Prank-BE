from app.langchain.scenarios.state import ScenarioCreateRequest
from langchain_openai import ChatOpenAI
from app.schemas.scenario import ScenarioFollowUpResponse
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.prompts.base_prompts import BASE_SYSTEM_PROMPT, get_language_specific_context, FOLLOWUP_SYSTEM_PROMPT
from typing import List

class ScenarioFollowUp:
    def __init__(self, model_name: str = "gpt-4.1"):

        self.model_name = model_name
        self.llm = ChatOpenAI(model=self.model_name, temperature=0.3).with_structured_output(ScenarioFollowUpResponse)

        self.follow_up_system_prompt = FOLLOWUP_SYSTEM_PROMPT
        

    async def generate_follow_up_questions(self, scenario_data: ScenarioCreateRequest) ->  ScenarioFollowUpResponse:
        follow_up_prompt = self.__build_follow_up_system_prompt(scenario_data)
        context = f"""
        Scenario Request:
        Title: {scenario_data.title}
        Description: {scenario_data.description}
        Target Name: {scenario_data.target_name}
        Language: {scenario_data.language.value if hasattr(scenario_data.language, 'value') else str(scenario_data.language)}
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", follow_up_prompt),
            ("user", context)
        ])

        chain = prompt | self.llm
        result = await chain.ainvoke({})
        return result

    def __build_follow_up_system_prompt(self, scenario_data: ScenarioCreateRequest) -> str:

        complete_prompt = self.follow_up_system_prompt
        complete_prompt += "\n\n" + get_language_specific_context(scenario_data.language)        

        return complete_prompt
    