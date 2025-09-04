"""
Enhancement node - improves existing voice lines based on user feedback
"""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.state import ScenarioState
from app.langchain.prompts.core_principles import CORE_PRINCIPLES, GOOD_EXAMPLES
from app.core.logging import console_logger


class EnhancementOutput(BaseModel):
    """Structured output for enhancement"""
    enhanced_lines: Dict[str, List[str]] = Field(
        description="Enhanced voice lines by type"
    )
    changes_made: List[str] = Field(
        description="List of improvements made"
    )


async def enhancer_node(state: ScenarioState) -> dict:
    """
    Enhance existing voice lines based on user feedback
    
    This node is called when user provides feedback on generated content
    """
    console_logger.info("Running enhancer node with user feedback")
    
    if not state.tts_lines or not hasattr(state, 'user_feedback'):
        console_logger.warning("No lines to enhance or no feedback provided")
        return {}
    
    system_prompt = f"""
        {CORE_PRINCIPLES}

        You are enhancing existing prank call lines based on user feedback.

        CURRENT CHARACTER:
        - Name: {state.analysis.persona_name if state.analysis else "Unknown"}
        - Company: {state.analysis.company_service if state.analysis else "Unknown"}
        - Voice: {state.analysis.voice_hints if state.analysis and state.analysis.voice_hints else "Standard"}

        USER FEEDBACK: The user wants these specific improvements.

        ENHANCEMENT RULES:
        1. KEEP the same character and scenario
        2. MAINTAIN the deadpan-serious tone
        3. ADDRESS the user's specific feedback
        4. PRESERVE what's working well
        5. Only change what needs improvement

        QUALITY TARGETS:
        - More believable (if requested)
        - More serious/less obvious (if requested)  
        - Better flow/naturalness (if requested)
        - Stronger character voice (if requested)

        USE THESE EXAMPLES AS REFERENCE:
        {GOOD_EXAMPLES}
    """
        
    user_prompt = """
        CURRENT LINES:
        {current_lines}

        USER FEEDBACK:
        {feedback}

        Enhance these lines based on the feedback. Keep what works, improve what doesn't.

        List the specific changes you made.

        Generate in {language} language.
    """
    
    # Format current lines
    current_lines_text = ""
    for voice_type, lines in state.tts_lines.items():
        current_lines_text += f"\n{voice_type}:\n"
        for i, line in enumerate(lines, 1):
            current_lines_text += f"  {i}. {line}\n"
    
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.3)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm.with_structured_output(EnhancementOutput)
    
    try:
        result = await chain.ainvoke({
            "current_lines": current_lines_text,
            "feedback": getattr(state, 'user_feedback', ''),
            "language": getattr(state.scenario_data.language, 'value', 'de')
        })
        
        console_logger.info(f"Enhancement complete. Changes: {', '.join(result.changes_made)}")
        
        # Update state with enhanced lines
        return {
            "tts_lines": result.enhanced_lines,
            "enhancement_changes": result.changes_made,
            "was_enhanced": True
        }
        
    except Exception as e:
        console_logger.error(f"Enhancement failed: {str(e)}")
        return {}


async def enhance_single_line(
    line_text: str,
    line_type: str,
    user_feedback: str,
    persona_name: str,
    company_service: str,
    language: str = "de"
) -> str:
    """
    Enhance a single voice line (for targeted enhancement)
    """
    system_prompt = f"""
        {CORE_PRINCIPLES}

        You are {persona_name} from {company_service}.

        Enhance this single {line_type} line based on user feedback.
        Keep the deadpan-serious tone.
        Make it sound natural but professional.
        """
            
    user_prompt = """
        CURRENT LINE:
        {line}

        USER FEEDBACK:
        {feedback}

        Provide ONE enhanced version that addresses the feedback.
        Keep the same language ({language}).
    """
    
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.3)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({
            "line": line_text,
            "feedback": user_feedback,
            "language": language
        })
        
        return result.content.strip().strip('"')
        
    except Exception as e:
        console_logger.error(f"Single line enhancement failed: {str(e)}")
        return line_text  # Return original if enhancement fails
