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
import random 


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
            - Create urgency 
            - Use the target's name if needed
            - Stay believable and professional
            - Explain why you are calling without being weird while opening the call. 
            - Keep it short: 12–30 words per sentence, max 2 sentence
        """,
        "QUESTION": """
            QUESTION - Questions during conversation:
            - ONLY real QUESTIONS, no statements or explanations
            - Escalate from normal to absurd 
            - Sparse "Mr./Mrs. [Name]" in questions - it's unnatural
            - Avoid repetition - each question different
        """,
        "RESPONSE": """
            RESPONSE - Reactions to objections:
            - Think of likely objections the target might raise and create fitting responses accordingly
            - DO NOT REACT TO YOUR OWN QUESTIONS THAT ARE GIVEN AS CONTEXT
            - Stay in character
            - Get slightly annoyed at too many questions
            - Redirect back to main topic
            - Vary strategies across lines (do not repeat the same approach):
              • clarify politely • deflect to a process/rule • mild apology + redirect • uncertainty / "not sure" • bureaucratic delay/transfer • misinterpret (lightly) then correct • soft pushback • escalate slightly
            - Do NOT always assure that details are correct (avoid repeating "the system shows", "we have confirmation"). Treat the premise as your belief, not an objective fact.
            - OPTIONAL: Include a clear 'Mittelteil' line that reiterates the premise and justifies it briefly (double down) in at most one response; keep it to max 1 sentence when used.
        """,
        "CLOSING": """
            CLOSING - End of conversation:
            - End politely but firmly
            - Mention the absurd thing casually again
            - Stay in character
            - Use the name for goodbye
            - Keep it short: 12-30 words per sentence, max 2 sentence
        """,
        "FILLER": """
            FILLER - Natürliche Pausen und Füllwörter:
            - Nutze natürliche Pausen mit "..." oder kurze Zwischenlaute
            - Pro Zeile 1 Füller/Ausrufe zufällig aus: "Ja", "Nein", "hmm"/"hmmm"/"ähm", "Okay", "Mhm", "Bitte?", "Wie bitte?", "Können Sie das nochmal wiederholen?", "Einen Moment", "Sekunde"
            - Über alle FILLER-Zeilen hinweg hohe Varianz: Wiederhole nicht dieselbe Phrase in zwei aufeinanderfolgenden Zeilen
            - Interrogative Füller wie "Wie bitte?" oder "Können Sie das nochmal wiederholen?" höchstens einmal im gesamten Set verwenden
            - Kurz halten (1–6 Wörter)
            - Es soll immer mindstens einmal ein "Ja", "Nein", oder "hmm" geben als kure Antworten!
        """
    }
    return instructions.get(voice_type, instructions["OPENING"])


async def generate_for_type(state: ScenarioState, voice_type: str) -> List[str]:
    """Generate lines for a specific voice type"""
    
    
    # Check for voice hints from analyzer
    voice_context = ""
    if hasattr(state.analysis, 'voice_hints') and state.analysis.voice_hints:
        voice_context = f"\nCHARACTER VOICE: {state.analysis.voice_hints}"
    
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


    """

    # GOOD EXAMPLES:
    # {kleber_generator_example}
    # {refugee_camp_generator_example}
    # {trash_generator_example}

    # Include relevant examples
    examples_text = ""
    examples = GOOD_EXAMPLES.get(voice_type, [])
    if examples:
        pick = random.sample(examples, k=1)
        examples_text = "\nStyle cues (do not copy; use only the vibe):\n" + "".join(f"- {e}\n" for e in pick)

    user_prompt = """
        Generate {count} {voice_type} lines for a prank call.

        Scenario: {title}
        Description: {description}
        Target Name: {target_name}

        {examples_text}

        Create {count} DIFFERENT variations.
        Ensure each variation uses a different conversational strategy (clarify, deflect, mild apology + redirect, uncertainty, bureaucratic delay, soft pushback, slight escalation, misread-then-correct).
        Return ONLY the spoken lines, no quotation marks.
        Each line should sound natural and believable.
        Keep each line very short (6–12 words), max 1 sentence.
        Generate in {language} language.
    """

    temp = 0.7 if voice_type in ["OPENING", "CLOSING"] else 0.9
    llm = ChatOpenAI(
        model="gpt-4.1-mini",
        temperature=temp,
        model_kwargs={"top_p": 0.95, "frequency_penalty": 0.5, "presence_penalty": 0.3}
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
            "title": state.title,
            "description": state.scenario_description or "",
            "target_name": state.target_name,
            "examples_text": examples_text,
            "language": state.language
        })
        
        # Clean up lines
        lines = []
        for line in result.lines:
            cleaned = line.strip().strip('"\'')
            if cleaned:
                lines.append(cleaned)
        
        console_logger.debug(f"Generated {len(lines)} {voice_type} lines")
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