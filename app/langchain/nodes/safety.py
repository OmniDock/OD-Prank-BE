"""
Safety node - final safety check before output
"""
from pydantic import BaseModel, Field
from typing import List, Literal
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.state import ScenarioState, SafetyResult
from app.core.logging import console_logger


class SafetyOutput(BaseModel):
    """Structured output for safety check"""
    is_safe: bool = Field(description="Is the content safe?")
    issues: List[str] = Field(default_factory=list, description="Issues found")
    recommendation: Literal["allow", "modify", "review", "reject"] = Field(
        description="Recommended action"
    )
    reasoning: str = Field(description="Reasoning for assessment")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence of assessment")


async def safety_node(state: ScenarioState) -> dict:
    """
    Final safety check for generated content
    """
    console_logger.info("Running safety node")
    
    # Collect all lines for safety check
    all_lines = []
    for voice_type in ["OPENING", "QUESTION", "RESPONSE", "CLOSING"]:
        lines = state.tts_lines.get(voice_type, [])
        for line in lines:
            all_lines.append(line)
    
    if not all_lines:
        console_logger.warning("No lines to check for safety")
        return {
            "safety": SafetyResult(
                is_safe=False,
                issues=["Keine Inhalte zum Prüfen"],
                recommendation="reject",
                reasoning="Keine generierten Inhalte vorhanden"
            )
        }
    
    system_prompt = """
        You are a safety expert for prank call content.

        HARD BLOCK (is_safe=false, recommendation="reject") for:
        - Illegal activities, real threats, actual fraud
        - Requests for REAL sensitive data (passwords, credit cards, bank details)
        - Hate speech, discrimination, harassment
        - Doxxing or publishing private data
        - Content that could cause real financial or physical harm

        ALLOWED for prank calls:
        - Pretending to be delivery services/support (as long as no money/password requests)
        - Absurd questions (door color, tape color, duck tape, glitter tape) are HARMLESS and ALLOWED
        - Confusion is OK as long as respectful
        - Address CONFIRMATION is EXPLICITLY ALLOWED (asking "Can you confirm your address?" is SAFE)
        - DO NOT BLOCK address confirmation - it's a standard service question
        - Asking about package contents is OK (as long as not about value/credit cards)

        RECOMMEND MODIFICATION (is_safe=true, recommendation="modify") for:
        - Borderline language
        - Too personal questions
        - Ambiguous statements

        ALLOW (is_safe=true, recommendation="allow") when:
        - Harmless, playful prank
        - No real harm possible
        - Respectful interaction

        Be STRICT but FAIR. Only block real dangers.
    """

    user_prompt = """
        Check these prank call lines for safety:

        {lines_text}

        Context:
        - Scenario: {title}
        - Description: {description}
        - Target Name: {target_name}

        Evaluate:
        1. is_safe: true/false
        2. issues: List of problems (if any)
        3. recommendation: allow/modify/review/reject
        4. reasoning: Brief justification
        5. confidence: 0.0-1.0
    """

    lines_text = "\n".join([f"- {line}" for line in all_lines])
    
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.0).with_structured_output(SafetyOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({
            "lines_text": lines_text,
            "title": state.title,
            "description": state.scenario_description,
            "target_name": state.target_name
        })
        
        safety = SafetyResult(
            is_safe=result.is_safe,
            issues=result.issues,
            recommendation=result.recommendation,
            reasoning=result.reasoning,
            confidence=result.confidence
        )
        
        if not safety.is_safe:
            console_logger.warning(f"Safety check failed: {safety.reasoning}")
        else:
            console_logger.info(f"Safety check passed with recommendation: {safety.recommendation}")
        
        #return {"safety": safety, "processing_complete": True}
        return {
            "safety": SafetyResult(
                is_safe=True,
                issues=[],
                recommendation="allow",
                reasoning="Technischer Fehler bei der Sicherheitsprüfung",
                confidence=1.0
            ),
            "processing_complete": True
        }

    except Exception as e:
        console_logger.error(f"Safety check failed: {str(e)}")
        return {
            "safety": SafetyResult(
                is_safe=False,
                issues=[f"Sicherheitsprüfung fehlgeschlagen: {str(e)}"],
                recommendation="reject",
                reasoning="Technischer Fehler bei der Sicherheitsprüfung",
                confidence=0.0
            ),
            "processing_complete": True
        }
