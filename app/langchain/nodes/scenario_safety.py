from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List, Literal

from app.schemas.scenario import ScenarioCreateRequest
from app.core.logging import console_logger
from app.langchain.scenarios.state import VoiceLineState, SafetyCheckResult, ScenarioAnalysisResult




class ScenarioSafetyChecker:
    """Handles scenario-level safety checks with structured output"""
    
    def __init__(self, model_name: str = "gpt-4.1"):
        
        self.llm = ChatOpenAI(model=model_name, temperature=0.1).with_structured_output(SafetyCheckResult)
        
        self.base_safety_prompt = """ 
                You are an expert content safety moderator for a prank call application.

                Goal: Allow playful, light-hearted pranks to proceed while strictly blocking genuinely harmful or illegal content.

                SAFETY CRITERIA (categorize any issues you find):
                - Harassment: Repeated unwanted contact, bullying, intimidation
                - Illegal: Activities that violate laws (fraud, threats, impersonation of authorities)
                - Harmful_targeting: Attacking vulnerable groups, protected characteristics
                - Excessive_cruelty: Causing genuine distress, psychological harm
                - Privacy_violation: Sharing personal information (doxxing, recording without consent)
                - Discrimination: Content based on race, gender, religion, etc.
                - Offensive_language: Profanity, slurs, inappropriate content

                DECISION POLICY (be precise and conservative for hard cases):
                - HARD BLOCK (set is_safe = false, recommendation = "reject", severity = "high" or "critical") when any of the following are present:
                  • Illegal with real-world harm, threats, crime instructions, or impersonation of authorities intended to defraud
                  • Privacy_violation such as doxxing, exposing personal identifiers, or coercive data collection
                  • Harmful_targeting or Discrimination with explicit hate, dehumanization, or incitement
                  • Excessive_cruelty intended to cause serious distress or fear
                - SOFT ALLOW/MODIFY (set is_safe = true, recommendation = "modify"; severity = "low" or "medium") for borderline content that can be made safe by small changes
                  • Mild Offensive_language, light teasing, ambiguous intent, satirical impersonation without fraud
                  • Provide 1–3 specific modifications in issues to make it safe (e.g., "remove profanity", "avoid personal data", "keep tone playful")
                - ALLOW (set is_safe = true, recommendation = "allow") when content is clearly playful and harmless
                - REVIEW (set is_safe = true, recommendation = "review") only if truly ambiguous. Prefer "modify" over "review" to reduce unnecessary blocking.

                CONFIDENCE HANDLING:
                - If confidence < 0.5, do NOT reject unless a HARD BLOCK condition is clearly triggered.

                ASSESSMENT GUIDELINES:
                - Consider cultural context and language
                - Evaluate intent vs. potential harm
                - Balance humor with respect and realism
                - Consider the target's likely reaction

                Output MUST follow the structured schema.
                Provide concise reasoning.
                """

        
    
    async def check_initial_safety(self, scenario_data: ScenarioCreateRequest) -> SafetyCheckResult:
        """Check scenario safety with structured output"""
        console_logger.info(f"Checking safety for scenario: {scenario_data.title}")

        initial_hard_filter_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", """
                    You are a HARD FILTER for prank scenarios. Block ONLY severe illegality/harm.
                    Set is_safe=false and recommendation="reject" ONLY if any of these are clearly present:
                    - Illegal activities with real-world harm or threats, crime instructions
                    - Fraud/impersonation of authorities intended to obtain money/credentials or similar 
                    - Harmful_targeting/Discrimination: explicit hate, dehumanization, incitement
                    - Excessive_cruelty intended to cause serious distress or fear

                    Otherwise set is_safe=true and recommendation="allow".
                    If confidence < 0.6, prefer is_safe=true unless a hard condition is explicit.
                    Output MUST follow the structured schema, keep reasoning concise.
                 
                """),
                ("user", """
                 
                    I am looking to create a prank call with the following details: 
                
                    SCENARIO DETAILS:
                    Title: {title}
                    Description: {description}
                    Target Name: {target_name}
                    Language: {language}
                 
                    Evaluate for safety issues and provide your assessment. 
                 
                """)
            ]
        )

        chain = initial_hard_filter_prompt | self.llm

        result = await chain.ainvoke({
            "title": scenario_data.title,
            "description": scenario_data.description,
            "target_name": scenario_data.target_name,
            "language": scenario_data.language
        })

        return result
    

    async def check_overall_safety(self, scenario_data: ScenarioCreateRequest, voice_lines: List[VoiceLineState], scenario_analysis: ScenarioAnalysisResult) -> SafetyCheckResult:
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
                 
                    Scenario Analysis:
                    {scenario_analysis}
                 
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
            "voice_lines": voice_lines,
            "scenario_analysis": scenario_analysis
        })

        console_logger.info(f"Overall safety check result: {result}")

        return result