"""
Analyzer node - creates persona and conversation plan
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.state import ScenarioState, ScenarioAnalysis
from app.langchain.prompts.core_principles_en import DEADPAN_PRINCIPLES, get_language_guidelines
from app.core.logging import console_logger


class AnalysisOutput(BaseModel):
    """Structured output for analysis"""
    persona_name: str = Field(description="Name of the caller")
    company_service: str = Field(description="Company/Service/Authority")
    conversation_goals: List[str] = Field(description="2-3 conversation goals")
    believability_anchors: List[str] = Field(description="3 believable details")
    escalation_plan: List[str] = Field(description="3 stages: normal → odd → absurd")
    cultural_context: str = Field(description="Cultural context (2-3 sentences)")
    voice_hints: Optional[str] = Field(
        default=None,
        description="Voice/accent hints from scenario (e.g., 'Italian pizza delivery' → 'enthusiastic, slightly rushed')"
    )


async def analyzer_node(state: ScenarioState) -> dict:
    """
    Analyze scenario and create persona with conversation plan
    """
    console_logger.info("Running analyzer node")
    
    system_prompt = f"""
{DEADPAN_PRINCIPLES}

{get_language_guidelines(getattr(state.scenario_data.language, 'value', 'de'))}

You create a believable persona for a prank call.

CRITICAL: FOLLOW ALL SPECIFIC INSTRUCTIONS FROM THE SCENARIO!
- If scenario mentions "Italian pizza delivery" → Make persona Italian, mention pizza shop name
- If scenario mentions "Indian tech support" → Make persona Indian, use appropriate name
- If scenario mentions specific characteristics → INCORPORATE THEM

IMPORTANT:
- Use REAL, known entities (DHL, Telekom, Pizza shops, etc.) 
- NO made-up company names like "ServicePlus24" UNLESS specified in scenario
- If no specific company fits, use generic terms ("Technical Support", "Building Management")
- RESPECT cultural/accent hints from the scenario description
- Escalation should be subtle: normal → slightly odd → one absurd question
"""

    user_prompt = """
Create a prank call persona for this scenario:

Title: {title}
Description: {description}
Target Name: {target_name}
Language: {language}
{clarifications_text}

EXTRACT FROM DESCRIPTION:
- Any nationality/accent mentioned? (e.g., "Italian pizza delivery" → Italian persona)
- Any specific company mentioned? (e.g., "Pizza Roma" → use that exact name)
- Any personality traits? (e.g., "nervous", "rushed", "overly friendly")

Provide:
1. persona_name: Match the nationality if mentioned (e.g., Italian → "Mario", Indian → "Raj")
2. company_service: Use exact company if mentioned, otherwise realistic entity
3. conversation_goals: 2-3 specific goals
4. believability_anchors: 3 realistic details that make it believable
5. escalation_plan: 3 stages (normal → odd → absurd but deadpan)
6. cultural_context: Brief cultural context
7. voice_hints: IF accent/nationality mentioned, note it (e.g., "Italian accent - enthusiastic about pizza")

Return all text in {language} language.
"""

    # Add clarifications if available
    clarifications_text = ""
    if state.clarifications and state.clarifying_questions:
        clarifications_text = "\nAdditional Information:\n"
        # Pair questions with answers
        for i, question in enumerate(state.clarifying_questions):
            if i < len(state.clarifications):
                answer = state.clarifications[i]
                clarifications_text += f"- Question: {question}\n  Answer: {answer}\n"

    llm = ChatOpenAI(model="gpt-4.1", temperature=0.3).with_structured_output(AnalysisOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({
            "title": state.scenario_data.title,
            "description": state.scenario_data.description or "",
            "target_name": state.scenario_data.target_name,
            "language": getattr(state.scenario_data.language, 'value', str(state.scenario_data.language)),
            "clarifications_text": clarifications_text
        })
        
        analysis = ScenarioAnalysis(
            persona_name=result.persona_name,
            company_service=result.company_service,
            conversation_goals=result.conversation_goals[:3],
            believability_anchors=result.believability_anchors[:3],
            escalation_plan=result.escalation_plan[:3],
            cultural_context=result.cultural_context
        )
        
        console_logger.info(f"Created persona: {analysis.persona_name} from {analysis.company_service}")
        return {"analysis": analysis}
        
    except Exception as e:
        console_logger.error(f"Analyzer failed: {str(e)}")
        # Fallback analysis
        return {
            "analysis": ScenarioAnalysis(
                persona_name="Technischer Support",
                company_service="Kundenservice",
                conversation_goals=["Problem klären", "Information sammeln"],
                believability_anchors=["Systemfehler", "Dringende Angelegenheit"],
                escalation_plan=["Normal fragen", "Merkwürdige Details", "Absurde Anfrage"],
                cultural_context="Deutscher Kontext, formelle Anrede"
            )
        }
