from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List, Literal

from app.schemas.scenario import ScenarioCreateRequest
from app.core.logging import console_logger
from app.langchain.scenarios.state import VoiceLineState


class SafetyCheckResult(BaseModel):
    """Structured output for safety checks"""
    is_safe: bool = Field(description="Whether the content is safe")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in safety assessment (0-1)")
    severity: Literal["low", "medium", "high", "critical"] = Field(description="Risk severity level")
    issues: List[str] = Field(description="List of specific safety concerns found")
    categories: List[Literal["harassment", "illegal", "harmful_targeting", "excessive_cruelty", "privacy_violation", "discrimination", "offensive_language"]] = Field(
        description="Categories of safety issues identified"
    )
    recommendation: Literal["allow", "review", "modify", "reject"] = Field(description="Recommended action")
    reasoning: str = Field(description="Brief explanation of the safety assessment")



class ScenarioSafetyChecker:
    """Handles scenario-level safety checks with structured output"""
    
    def __init__(self, model_name: str = "gpt-4o"):
        
        self.llm = ChatOpenAI(model=model_name, temperature=0.1).with_structured_output(SafetyCheckResult)
        
        self.base_safety_prompt = """ 
                
                You are an expert content safety moderator for a prank call application. 

                Your role is to evaluate prank scenarios for potential safety issues while maintaining a balance between fun and harm prevention.

                SAFETY CRITERIA:
                - Harassment: Repeated unwanted contact, bullying, intimidation
                - Illegal: Activities that violate laws (fraud, threats, impersonation of authorities)
                - Harmful targeting: Attacking vulnerable groups, protected characteristics
                - Excessive cruelty: Causing genuine distress, psychological harm
                - Privacy violation: Sharing personal information
                - Discrimination: Content based on race, gender, religion, etc.
                - Offensive language: Profanity, slurs, inappropriate content

                ASSESSMENT GUIDELINES:
                - Consider cultural context and language
                - Evaluate intent vs. potential harm
                - Balance humor with respect
                - Consider target's likely reaction

                Provide detailed reasoning for your assessment.
                """

        
    
    async def check_initial_safety(self, scenario_data: ScenarioCreateRequest) -> SafetyCheckResult:
        """Check scenario safety with structured output"""
        console_logger.info(f"Checking safety for scenario: {scenario_data.title}")

        initial_safety_prompt = ChatPromptTemplate.from_messages(
            [           
                ("system", self.base_safety_prompt),
                ("user", """
                
                    SCENARIO DETAILS:
                    Title: {title}
                    Description: {description}
                    Target Name: {target_name}
                    Language: {language}

                    Evaluate for safety issues and provide your assessment.
                 
                """
                )
            ]
        )

        chain = initial_safety_prompt | self.llm
    
        result = await chain.ainvoke({
            "title": scenario_data.title,
            "description": scenario_data.description,
            "target_name": scenario_data.target_name,
            "language": scenario_data.language
        })

        return result
    

    async def check_overall_safety(self, scenario_data: ScenarioCreateRequest, voice_lines: List[VoiceLineState]) -> SafetyCheckResult:
        """Check scenario safety with structured output"""
        console_logger.info(f"Checking safety for scenario: {scenario_data.title}")

        overall_safety_prompt = ChatPromptTemplate.from_messages(
            [
            
                ("system", self.base_safety_prompt),
                ("user", """

                    Scenario Details:
                    Title: {title}
                    Description: {description}
                    Target Name: {target_name}
                    Language: {language}
                 
                    Voice Lines:
                    {voice_lines}

                    Evaluate for safety issues and provide your assessment.
                 
                """
                )
            ]
        )

        chain = overall_safety_prompt | self.llm
    
        result = await chain.ainvoke({
            "title": scenario_data.title,
            "description": scenario_data.description,
            "target_name": scenario_data.target_name,
            "language": scenario_data.language,
            "voice_lines": voice_lines
        })

        return result