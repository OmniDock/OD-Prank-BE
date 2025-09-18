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
            - Escalate from normal to absurd 
            - Sparse "Mr./Mrs. [Name]" in questions - it's unnatural
            - Avoid repetition - each question different
            - This not the type for greeting or re-introductions.
        """,
        "RESPONSE": """
            RESPONSE - Reactions to objections:
            - Think of reactions the React the target is likely to give and create fitting responses accordingly. 
            - For example, disbelief in the authenticity or reason for the call. 
            - e.g. "Didn't you hear from this topic? Everyone talks about this situation. <some more context>"
            - Double down and repeat the Opening with a little more context and with different wording.
            - Defend your statements and why you are calling. 
            - Stay in character and keep it believable. 
            - Add some random facts here to distract from questions asked by the target or also keep the conversation going.
            - Add random facts here to keep the conversation going.
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
            - MUST include atleast one 'yes' and alteast one 'no' filler 
            - Use natural pauses with "..." or fillers
            - No repetition - each filler different
            - Keep them short and concise. 
            - You need to include in the set of Voice Lines (Do not alter these or make sentences out of the following fillers):
                - "Yes"
                - "No"
                - "Moment"
                - "Sorry?"
            - The rest can be a little more creative. 
        """
    }
    return instructions.get(voice_type, instructions["OPENING"])


async def generate_for_type(state: ScenarioState, voice_type: str) -> List[str]:
    """Generate lines for a specific voice type"""

    if not state.analysis:
        console_logger.error(f"Analyzer data missing before generating {voice_type} lines")
        return state.plain_lines.get(voice_type, [])[: state.target_counts.get(voice_type, 2)]

    voice_context = ""
    if state.analysis.voice_hints:
        voice_context = f"\nCHARACTER VOICE: {state.analysis.voice_hints}"

    examples_text = ""
    if voice_type in GOOD_EXAMPLES:
        examples_text = (
            "\nGood examples for inspiration (DON'T copy, just use the style, length, context depth for this type of Voice Line, randomness, facts, etc.):\n"
        )
        for example in GOOD_EXAMPLES[voice_type]:
            examples_text += f"- {example}\n"

    user_prompt = """
        Generate {count} {voice_type} lines for a prank call.

        Scenario: {title}
        Description: {description}
        Target Name: {target_name}

        {examples_text}

        Create exactly {count} DIFFERENT variations.
        Return ONLY the spoken lines, no quotation marks.
        Each line should sound natural and believable.
        Generate in {language} language.
    """

    llm = ChatOpenAI(
        model="gpt-4.1-mini",
        temperature=0.4 if voice_type in ["OPENING", "CLOSING", "FILLER"] else 0.6,
    ).with_structured_output(GeneratorOutput)

    target_count = state.target_counts.get(voice_type, 2)
    collected: List[str] = list(state.plain_lines.get(voice_type, []))
    max_attempts = 3
    attempts = 0

    try:
        while len(collected) < target_count and attempts < max_attempts:
            system_prompt = f"""
                {CORE_PRINCIPLES}

                You are {state.analysis.persona_name} from {state.analysis.company_service}.{voice_context}
                Your goals: {', '.join(state.analysis.conversation_goals)}
                Believable details: {', '.join(state.analysis.believability_anchors)}
                Escalation: {' → '.join(state.analysis.escalation_plan)}

                {get_type_instructions(voice_type)}

                IMPORTANT RULES:
                - No obvious jokes
                - Maximum ONE absurd detail 
                - ALWAYS stay in character
                - NO REPETITION - each line must be unique
                - Avoid excessive name usage 
                - Your tone and workd choice needs to match the character you are including their cultuaral context and how that person would do the escalation plan
               
                {_get_already_generated_lines_prompt(state)}

                FULL SCENARIO EXAMPLES AS REFERENCE ONLY:
                {kleber_generator_example}
                {refugee_camp_generator_example}
                {trash_generator_example}
            """

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", user_prompt),
            ])

            chain = prompt | llm

            remaining = max(target_count - len(collected), 0)
            if remaining == 0:
                break

            result = await chain.ainvoke(
                {
                    "count": remaining,
                    "voice_type": voice_type,
                    "title": state.title,
                    "description": state.scenario_description or "",
                    "target_name": state.target_name,
                    "examples_text": examples_text,
                    "language": state.language,
                }
            )

            new_lines = []
            for line in result.lines:
                cleaned = line.strip().strip('"\'')
                if cleaned and cleaned not in collected:
                    new_lines.append(cleaned)

            collected.extend(new_lines)
            state.plain_lines[voice_type] = collected
            attempts += 1

            console_logger.debug(
                f"Attempt {attempts} generated {len(collected)}/{target_count} {voice_type} lines"
            )

            if not new_lines:
                console_logger.warning(
                    f"No new {voice_type} lines generated on attempt {attempts}"
                )

        if len(collected) < target_count:
            console_logger.warning(
                f"Only generated {len(collected)} of {target_count} {voice_type} lines after {attempts} attempts"
            )

        return collected[:target_count]

    except Exception as e:
        console_logger.error(f"Generation failed for {voice_type}: {str(e)}")
        return collected[:target_count]
    


async def generator_node(state: ScenarioState) -> dict:
    """
    Generate plain voice lines for all types
    """
    console_logger.info("Running generator node")
    
    
    for voice_type in ["OPENING", "QUESTION", "RESPONSE", "CLOSING", "FILLER"]:
        lines = await generate_for_type(state, voice_type)
        state.plain_lines[voice_type] = lines
        
    return {"plain_lines": state.plain_lines}



def _get_already_generated_lines_prompt(state: ScenarioState) -> str:
    """Get already generated lines as a prompt"""
    prompt_start_template = '''
    - Use the context of the lines you already came up with for new lines. These are YOUR OWN lines and NOT the targets questions or responses. DO NOT RESPOND TO YOUR OWN LINES
      Think of the most likely responses or objections to your already generated lines that the target might give and create new lines based on those responses that fit you as the character, the scenario and progress the escalation. 

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
