"""
Generator node - creates plain voice lines
"""
from typing import List, Dict
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.state import ScenarioState
from app.langchain.prompts.core_principles import (
    CORE_PRINCIPLES, 
    get_language_guidelines,
    GOOD_EXAMPLES
)
from app.langchain.prompts.examples import kleber_generator_example, refugee_camp_generator_example, trash_generator_example
from app.core.logging import console_logger


class GeneratorOutput(BaseModel):
    """Structured output for generation"""
    lines: List[str] = Field(description="Generated voice lines")


def get_type_instructions(voice_type: str) -> str:
    """Get specific instructions for each voice line type"""
    instructions = {
        "OPENING": """
            OPENING - First contact:
            - Introduce yourself (name/role/company)
            - State the reason for calling
            - Establish authority and credibility (e.g. Neighbor, Volunteer Group Leader, etc.)
            - Create mild urgency 
            - Use the target's name
            - Stay believable and professional
        """,
        "QUESTION": """
            QUESTION - Questions during conversation:
            - ONLY real QUESTIONS, no statements or explanations
            - Escalate from normal to absurd (last question should be absurd)
            - Sparse "Mr./Mrs. [Name]" in questions - it's unnatural
            - Ask absurd question deadpan: "What color is your front door?"
            - Blame weird questions on "the system"
            - Avoid repetition - each question different
        """,
        "RESPONSE": """
            RESPONSE - Reactions to objections:
            - React to objections/questions
            - Stay in character
            - Blame problems on system/protocol
            - Get slightly annoyed at too many questions
            - Redirect back to main topic
        """,
        "CLOSING": """
            CLOSING - End of conversation:
            - End politely but firmly
            - Mention the absurd thing casually again
            - Stay in character
            - Use the name for goodbye
        """,
        "FILLER": """
            FILLER - Natural pauses and fillers:
            - Use natural pauses with "..." or fillers
            - Include a from 'yes', 'no' and 'right' or 'okay' that fits the character and the situation
            - No repetition - each filler different
        """
    }
    return instructions.get(voice_type, instructions["OPENING"])


async def generate_for_type(state: ScenarioState, voice_type: str) -> List[str]:
    """Generate lines for a specific voice type"""
    
    if not state.analysis:
        console_logger.error("No analysis available for generation")
        return []
    
    # Check for voice hints from analyzer
    voice_context = ""
    if hasattr(state.analysis, 'voice_hints') and state.analysis.voice_hints:
        voice_context = f"\nCHARACTER VOICE: {state.analysis.voice_hints}"
    
    system_prompt = f"""
        {CORE_PRINCIPLES}

        {get_language_guidelines(getattr(state.scenario_data.language, 'value', 'de'))}

        You are {state.analysis.persona_name} from {state.analysis.company_service}.{voice_context}
        Your goals: {', '.join(state.analysis.conversation_goals)}
        Believable details: {', '.join(state.analysis.believability_anchors)}
        Escalation: {' → '.join(state.analysis.escalation_plan)}

        {get_type_instructions(voice_type)}

        IMPORTANT RULES:
        - No obvious jokes
        - Maximum ONE absurd detail 
        - Use natural pauses with "..." or fillers sparingly
        - ALWAYS stay in character
        - NO REPETITION - each line must be unique
        - Avoid excessive name usage 
        {_get_already_generated_lines_prompt(state)}

        GOOD EXAMPLES:
        {kleber_generator_example}
        {refugee_camp_generator_example}
        {trash_generator_example}
    """

    # Include relevant examples
    examples_text = ""
    if voice_type in GOOD_EXAMPLES:
        examples_text = f"\nGood examples for inspiration (DON'T copy, just use the style):\n"
        for example in GOOD_EXAMPLES[voice_type][:3]:
            examples_text += f"- {example}\n"

    user_prompt = """
        Generate {count} {voice_type} lines for a prank call.

        Scenario: {title}
        Description: {description}
        Target Name: {target_name}

        {examples_text}

        Create {count} DIFFERENT variations.
        Return ONLY the spoken lines, no quotation marks.
        Each line should sound natural and believable.
        Generate in {language} language.
    """

    llm = ChatOpenAI(
        model="gpt-4.1", 
        temperature=0.4 if voice_type in ["OPENING", "CLOSING", "FILLER"] else 0.6
    ).with_structured_output(GeneratorOutput)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({
            "count": state.target_counts.get(voice_type, 2),
            "voice_type": voice_type,
            "title": state.scenario_data.title,
            "description": state.scenario_data.description or "",
            "target_name": state.scenario_data.target_name,
            "examples_text": examples_text,
            "language": getattr(state.scenario_data.language, 'value', str(state.scenario_data.language))
        })
        
        # Clean up lines
        lines = []
        for line in result.lines:
            cleaned = line.strip().strip('"\'')
            if cleaned:
                lines.append(cleaned)
        
        console_logger.info(f"Generated {len(lines)} {voice_type} lines")
        return lines[:state.target_counts.get(voice_type, 2)]
        
    except Exception as e:
        console_logger.error(f"Generation failed for {voice_type}: {str(e)}")
        return []
    


async def generator_node(state: ScenarioState) -> dict:
    """
    Generate plain voice lines for all types
    """
    console_logger.info("Running generator node")
    
    
    for voice_type in ["OPENING", "QUESTION", "RESPONSE", "CLOSING", "FILLER"]:
        lines = await generate_for_type(state, voice_type)
        state.plain_lines[voice_type] = lines
    
    total_lines = sum(len(lines) for lines in state.plain_lines.values())
    console_logger.info(f"Generated {total_lines} total lines")
    
    return {"plain_lines": state.plain_lines}



def _get_already_generated_lines_prompt(state: ScenarioState) -> str:
    """Get already generated lines as a prompt"""
    prompt_start_template = '''
    - Use the context of already generated lines for new lines. Think of the most likely responses to the already generated lines that the target of the prank call might give and 
        create new lines based on those responses that fit you as the character, the scenario and progress the escalation plan. 

    Already generated lines:
    '''
    generated_linese_prompt = ""
    for voice_type, lines in state.plain_lines.items():
        if lines:
            generated_linese_prompt += f"{voice_type}:\n"
            for line in lines:
                generated_linese_prompt += f"{line}\n"

    if generated_linese_prompt:
        generated_linese_prompt =  prompt_start_template + "\n" + generated_linese_prompt
    return generated_linese_prompt