from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.prompts.base_prompts import ENHANCEMENT_SYSTEM_PROMPT

class ScenarioEnhancer:
    def __init__(self, model_name: str = 'gpt-4.1'):
        self.model_name = model_name
        self.llm = ChatOpenAI(model=self.model_name, temperature=0.7)


    async def enhance_scenario(self, questions: List[str], answers: List[str], scenario_description: str) -> str:
        """Enhance scenario with questions and answers"""
        
        enhancement_prompt = ChatPromptTemplate.from_messages([
            ("system", ENHANCEMENT_SYSTEM_PROMPT),
            ("user", """
                Scenario Description:
                {scenario_description}
             
                Questions:
                {questions}
                
                Answers:
                {answers}
            """)
        ])
        
        chain = enhancement_prompt | self.llm
        
        result = await chain.ainvoke({
            "scenario_description": scenario_description,
            "questions": questions,
            "answers": answers
        })
        
        return result.content 