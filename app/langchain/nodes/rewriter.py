"""
Rewriter node - improves low-quality content using examples
"""
from typing import Dict, List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.state import ScenarioState
from app.langchain.prompts.core_principles import GOOD_EXAMPLES, CORE_PRINCIPLES
from app.core.logging import console_logger


class RewriteOutput(BaseModel):
    """Structured output for rewriting"""
    opening: List[str] = Field(description="Improved OPENING lines")
    question: List[str] = Field(description="Improved QUESTION lines")
    response: List[str] = Field(description="Improved RESPONSE lines")
    closing: List[str] = Field(description="Improved CLOSING lines")
    filler: List[str] = Field(description="Improved FILLER lines")


async def rewriter_node(state: ScenarioState) -> dict:
    """
    Rewrite low-quality lines (only called if quality < 0.7)
    """
    console_logger.info("Running rewriter node - improving low-quality content")
    
    if not state.quality:
        console_logger.warning("No quality assessment available")
        return {}
    
    system_prompt = f"""
        {CORE_PRINCIPLES}

        The generated lines have quality issues:
        - Seriousness: {state.quality.seriousness:.2f} (Target: > 0.7)
        - Believability: {state.quality.believability:.2f} (Target: > 0.7)
        - Judge notes: {state.quality.notes}

        YOUR TASK:
        1. Make lines MORE SERIOUS (less obviously funny)
        2. Make them MORE BELIEVABLE (like real service calls)
        3. Keep ONE absurd thing, but deliver it deadpan
        4. Shorten to max 10 words per sentence
        5. Remove youth slang and obvious jokes

        USE THESE PROVEN EXAMPLES AS TEMPLATES:
    """ 

    # Add good examples
    examples_text = ""
    for voice_type in ["OPENING", "QUESTION", "RESPONSE", "CLOSING", "FILLER"]:
        if voice_type in GOOD_EXAMPLES:
            examples_text += f"\n{voice_type} Examples:\n"
            for example in GOOD_EXAMPLES[voice_type][:2]:
                examples_text += f"- {example}\n"

    user_prompt = """
        ORIGINAL LINES THAT NEED IMPROVEMENT:

        OPENING:
        {opening_lines}

        QUESTION:
        {question_lines}

        RESPONSE:
        {response_lines}

        CLOSING:
        {closing_lines}

        FILLER:
        {filler_lines}


        {examples_text}

        Improve ALL lines. Make them:
        - More serious and believable
        - Shorter and more concise
        - More like the examples

        Return improved versions for each type.
        Keep the same language as the original lines.
    """

    def format_lines(lines: List[str]) -> str:
        if not lines:
            return "None"
        return "\n".join([f"- {line}" for line in lines])

    llm = ChatOpenAI(model="gpt-4.1", temperature=0.3).with_structured_output(RewriteOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({
            "opening_lines": format_lines(state.tts_lines.get("OPENING", [])),
            "question_lines": format_lines(state.tts_lines.get("QUESTION", [])),
            "response_lines": format_lines(state.tts_lines.get("RESPONSE", [])),
            "closing_lines": format_lines(state.tts_lines.get("CLOSING", [])),
            "filler_lines": format_lines(state.tts_lines.get("FILLER", [])),
            "examples_text": examples_text
        })
        
        # Clean up improved lines
        improved = {
            "OPENING": [],
            "QUESTION": [],
            "RESPONSE": [],
            "CLOSING": [],
            "FILLER": []
        }
        
        # Process each type
        for voice_type, lines in [
            ("OPENING", result.opening),
            ("QUESTION", result.question),
            ("RESPONSE", result.response),
            ("CLOSING", result.closing),
            ("FILLER", result.filler)
        ]:
            cleaned = []
            for line in lines:
                clean_line = line.strip().strip('"\'').lstrip('- ')
                if clean_line:
                    cleaned.append(clean_line)
            improved[voice_type] = cleaned
        
        console_logger.info("Successfully rewrote low-quality lines")
        
        return {
            "tts_lines": improved,
            "was_rewritten": True
        }
        
    except Exception as e:
        console_logger.error(f"Rewriter failed: {str(e)}")
        # Return original lines if rewriting fails
        return {"was_rewritten": False}
