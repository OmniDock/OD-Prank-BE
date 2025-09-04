"""
Clarifier node - detects missing information and generates questions
"""
from pydantic import BaseModel, Field, create_model
from typing import List, Optional, Type
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.state import ScenarioState
from app.core.logging import console_logger
from app.core.utils.enums import LanguageEnum

class ClarifierOutput(BaseModel):
    """Structured output for clarifier"""
    title: Optional[str] = Field(description="Title of the prank call scenario")
    target_name: Optional[str] = Field(description="Name of the target that is getting pranked")
    language: str = Field(description=f"Language of the prank call scenario. Must be one of: {', '.join([lang.value for lang in LanguageEnum])}")


async def extractor_node(state: ScenarioState) -> dict:
    """
    Check if critical information is missing and generate clarifying questions
    """
    console_logger.info("Running Extractor node")


    inital_prompt = f"""
        You are an expert comedy script analyst with 15+ years of experience in reviewing prank call scenarios.
        You are given description of a prank call scenario and tasked as follows:

        EXTRACT INFORMATION FROM DESCRIPTION:
        - The Name of the target that is getting pranked.
        - The Language of the prank call (must be one of: {', '.join([lang.value for lang in LanguageEnum])}). If not provided explicitly, use the language of the description.
        - IMPORTANT: If any of the above information is not available or cannot be determined from the description, set that field to None. Do not make assumptions or guess values.

        CREATE TITLE:
        - A short fitting title for the prank call scenario based on the description. Few words max.
        """
    
    user_prompt = """
        Extract the name of the target getting pranked and the language of the prank call description.
        Then create a short fitting title for the prank call scenario based on the description. Few words max.

        Description: 
        {description}
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2).with_structured_output(ClarifierOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", inital_prompt),
        ("user", user_prompt)
    ])
    chain = prompt | llm 
    
    try:
        result = await chain.ainvoke({
            "description": state.scenario_description
        })
        
        return {
                'title': result.title,
                'target_name': result.target_name,
                'language': result.language,
            }
    
    except Exception as e:
        console_logger.error(f"Clarifier failed: {str(e)}")
        return {
                'title': 'Prank', 
                'target_name': None,
                'language': None,
            }




