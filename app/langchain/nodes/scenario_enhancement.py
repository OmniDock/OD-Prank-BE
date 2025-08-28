from langchain_openai import ChatOpenAI
from app.schemas.scenario import ScenarioCreateRequest
from app.langchain.scenarios.state import ScenarioEnhancementState


class ScenarioEnhancer:
    def __init__(self, model_name: str = "gpt-4.1"):
        self.model_name = model_name
        self.llm = ChatOpenAI(model=self.model_name, temperature=0.6)

    async def enhance_scenario(self, scenario_data: ScenarioEnhancementState) -> ScenarioEnhancementState:
        from app.langchain.prompts.base_prompts import ENHANCEMENT_SYSTEM_PROMPT, get_language_specific_context
        from langchain_core.prompts import ChatPromptTemplate
        
        enhancement_prompt = ENHANCEMENT_SYSTEM_PROMPT + "\n\n" + get_language_specific_context(scenario_data.scenario_data.language)
        
        context = f"""
        Original Scenario:
        Title: {scenario_data.scenario_data.title}
        Description: {scenario_data.scenario_data.description}
        Target Name: {scenario_data.scenario_data.target_name}
        Language: {scenario_data.scenario_data.language.value if hasattr(scenario_data.scenario_data.language, 'value') else str(scenario_data.scenario_data.language)}

        Questions Asked:
        {chr(10).join([f"{i+1}. {q}" for i, q in enumerate(scenario_data.follow_up_questions)])}

        User Answers:
        {chr(10).join([f"{i+1}. {a}" for i, a in enumerate(scenario_data.answers)])}
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", enhancement_prompt),
            ("user", context)
        ])

        chain = prompt | self.llm
        result = await chain.ainvoke({})
        enhanced_description = result.content
        
        # Create enhanced scenario data
        enhanced_scenario = ScenarioCreateRequest(
            title=scenario_data.scenario_data.title,
            description=enhanced_description,
            target_name=scenario_data.scenario_data.target_name,
            language=scenario_data.scenario_data.language
        )
        
        # Update the state with enhanced scenario data
        scenario_data.enhanced_scenario_data = enhanced_scenario
        return scenario_data