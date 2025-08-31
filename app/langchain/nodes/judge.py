"""
Judge node - evaluates quality of generated content
"""
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.state import ScenarioState, QualityResult
from app.core.logging import console_logger


class JudgeOutput(BaseModel):
    """Structured output for quality judgment"""
    seriousness: float = Field(ge=0.0, le=1.0, description="How deadpan/serious (0-1)")
    believability: float = Field(ge=0.0, le=1.0, description="How believable (0-1)")
    subtle_emotion: float = Field(ge=0.0, le=1.0, description="Subtle emotional effect (0-1)")
    notes: str = Field(description="Brief quality notes")


async def judge_node(state: ScenarioState) -> dict:
    """
    Judge the quality of generated TTS lines
    """
    console_logger.info("Running judge node")
    
    # Collect all lines for evaluation
    all_lines = []
    for voice_type in ["OPENING", "QUESTION", "RESPONSE", "CLOSING"]:
        lines = state.tts_lines.get(voice_type, [])
        if lines:
            all_lines.append(f"\n{voice_type}:")
            for line in lines:
                all_lines.append(f"- {line}")
    
    if not all_lines:
        console_logger.warning("No lines to judge")
        return {
            "quality": QualityResult(
                seriousness=0.0,
                believability=0.0,
                subtle_emotion=0.0,
                notes="No lines to evaluate"
            )
        }
    
    system_prompt = """
You are an expert in prank call quality. Evaluate the generated lines.

EVALUATION CRITERIA:

SERIOUSNESS (0-1): How deadpan/serious are the lines?
- 1.0 = Completely deadpan, no detectable jokes
- 0.7 = Mostly serious with minimal humor elements
- 0.5 = Too obviously funny
- 0.0 = Open jokes, slang, breaking character

BELIEVABILITY (0-1): Could this be a real call?
- 1.0 = Completely believable, like a real service call
- 0.7 = Mostly believable with minor oddities
- 0.5 = Too many unrealistic elements
- 0.0 = Obviously fake

SUBTLE_EMOTION (0-1): Does it create the desired confusion?
- 1.0 = Perfect balance of normal and absurd
- 0.7 = Good confusion, could be more subtle
- 0.5 = Too direct or too normal
- 0.0 = No emotional effect

Give honest ratings. If something is bad, rate it low!
"""

    user_prompt = """
Evaluate these prank call lines:

{lines_text}

Context:
- Persona: {persona}
- Company: {company}
- Escalation: {escalation}

Provide scores from 0.0 to 1.0 for:
- seriousness (deadpan delivery)
- believability (credibility)
- subtle_emotion (subtle confusion)
- notes (what's good/bad?)
"""

    lines_text = "\n".join(all_lines)
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0).with_structured_output(JudgeOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({
            "lines_text": lines_text,
            "persona": state.analysis.persona_name if state.analysis else "Unknown",
            "company": state.analysis.company_service if state.analysis else "Unknown",
            "escalation": " → ".join(state.analysis.escalation_plan) if state.analysis else "None"
        })
        
        quality = QualityResult(
            seriousness=result.seriousness,
            believability=result.believability,
            subtle_emotion=result.subtle_emotion,
            notes=result.notes
        )
        
        console_logger.info(
            f"Quality scores - Seriousness: {quality.seriousness:.2f}, "
            f"Believability: {quality.believability:.2f}, "
            f"Emotion: {quality.subtle_emotion:.2f}"
        )
        
        return {"quality": quality}
        
    except Exception as e:
        console_logger.error(f"Judge failed: {str(e)}")
        return {
            "quality": QualityResult(
                seriousness=0.5,
                believability=0.5,
                subtle_emotion=0.5,
                notes=f"Evaluation failed: {str(e)}"
            )
        }