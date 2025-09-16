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
from app.core.logging import console_logger
import random 


class GeneratorOutput(BaseModel):
    """Structured output for generation"""
    lines: List[str] = Field(description="Generated voice lines")
def get_type_instructions(voice_type: str) -> str:
    """Get specific instructions for each voice line type"""
    instructions = {
        "OPENING": """
            OPENING - Point ofFirst contact:

            - Imagen you are starting a conversation with a target who does not know that this call will happen. Openers should introduce the scenario.

            - Usually this follows the 3 Rules i) Who is calling ii) What it's about iii) Why it matters right now (clear urgency / next step)
            - Introduce yourself (name/role/company)
            - State why you are calling and why it matters right now. 
            - Also include some justification for the call if present in the context. 

            - You can add a detail to make it more believable. 
            - Establish authority and credibility (e.g. Neighbor, Volunteer Group Leader, etc.)
            - Use the target's name if needed
            - Stay believable and professional
            - Make it straight forward to the point. Dont tell a whole story. Start a Conversation here. 
        """,
        "QUESTION": """
            QUESTION - Questions during the conversation to keep it interesting. Those are Mid Call Questions:
            - ONLY real QUESTIONS, no statements or explanations
            - Escalate from normal to absurd but keep it believable. 
            - Sparse "Mr./Mrs. [Name]" in questions - it's unnatural
            - Avoid repetition - each question different
            - Tie each question to a new angle (where to drop package, who can sign, how to handle your test ride, follow-up visit, etc.).
            - Never re-introduce yourself; treat every question as mid-call context (skip "Hallo"/"Guten Tag" greetings).
            - Keep it short and concise. 
            - Reference the premise succinctly, without re-delivering the full opening spiel.
        """,
        "RESPONSE": f"""
            RESPONSE - Reactions to objections or emphasis questions for the call itself:
            - Think of likely objections the target might raise and create fitting responses accordingly
            - Most RESPONSES should actively reiterate the premise and justify it briefly (double down) in a confident tone.
            - DO NOT REACT TO YOUR OWN QUESTIONS THAT ARE GIVEN AS CONTEXT
            - Ensure every response addresses a different hypothetical objection and references a fresh procedural or situational detail.
            - Keep it naturally and believable. Dont narrate on a whole story.
            - Stay in flow: no greetings, no self-introductions, no "Ich meld mich" framing — you are already in conversation.
            - The Rest follows answers to hypothetical questions.
            MANDATORY: Include AT LEAST one explicit doubling-down line that cites consensus or authority ("all the teachers agreed" / "the board signed this") and hints at consequence if ignored.

        """,
        "CLOSING": """
            CLOSING - End of conversation:
            - End politely but firmly
            - Mention the absurd thing casually again
            - Stay in character
            - Use the name for goodbye
            - Offer varied wrap-up actions (next delivery attempt, sending proof, leaving swing assembled, texting a photo, etc.) and avoid repeating language.
            - Keep it naturally and believable. Dont narrate on a whole story.
        """,
        "FILLER": """
            FILLER - Natürliche Pausen und Füllwörter:
            - Jede Zeile MUSS genau einen klaren Füller/Ausruf enthalten. Nutze eine Mischung aus:
                - "Ja"
                - "Nein"
                - "Einen Moment" / "Sekunde"
                - "Okay"
                - "Mhm"
                - "Bitte?"
                - "Wie bitte?"
                - "Können Sie das nochmal wiederholen?"
                - "hmm"/"hmmm"/"ähm"
            - Stelle sicher, dass über das gesamte Set hinweg "Ja", "Nein" und ein "Einen Moment bitte" vorkommen.
            - Über alle FILLER-Zeilen hinweg hohe Varianz: Wiederhole nicht dieselbe Phrase im Set.
            - Variiere die Zeichensetzung oder knappe Zusatzsilben, damit jede Zeile eine eigene Nuance bekommt.
            - Keine vollständigen Sätze oder zusätzlichen Aussagen – nur das Füllwort plus ggf. eine knappe bestätigende Silbe.
            - Interrogative Füller wie "Wie bitte?" oder "Können Sie das nochmal wiederholen?" können im Set vorkommen.
            - Ultra-kurz halten (1–4 Wörter) und mit natürlicher Pausen-Punktuation ("...", "–") kombinieren.
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

        You are {state.analysis.persona_name} from {state.analysis.company_service}. {voice_context}
        Your goals: {', '.join(state.analysis.conversation_goals)}
        Believable details: {', '.join(state.analysis.believability_anchors)}
        Escalation: {' → '.join(state.analysis.escalation_plan)}


        IMPORTANT GLOBAL RULES:
        - Voice Lines are Part of a Conversation. They should sound natural and believable. 
        - Each Voice Line stands alone but is part of a converstation. 
        - Each Voice Line Type should also stand alone but is still part of a conversation. For example the Opening should be a standalone line and each Line should contain all needed informations.
        - No obvious jokes; keep it straight-faced and believable
        - ALWAYS stay in character; never break the fourth wall
        - NO REPETITION — each line within a type must be unique in wording and idea. 
        - Avoid excessive name usage; at most once in OPENING, otherwise only if natural
        - Your tone and word choice must match the character, including their cultural context and how that person would execute the escalation plan
        - Do not hedge with "if you want"/"maybe" unless it's the chosen strategy
        - Forbidden: "AI", "as an AI", "language model", "script", "prompt", "prank"
        - No placeholders like [NAME]/[DATE]; always use natural wording without brackets
        VARIETY DIRECTIVES:
        - Each line must spotlight a different micro-context detail (timeline, location, logistics step, personal action, consequence, or follow-up).
        - Rotate sentence openings and key verbs; avoid multiple lines with the same skeleton such as "Hallo ..., hier ist".
        - When referencing a absurd hook, find fresh angles (what was checked, who approved, next steps) without contradicting earlier lines.

        Already generated Voice Lines Scripts for this scenario:
        {_get_already_generated_lines_prompt(state)}

        Instruction for this new type you should provide right now: 
        {get_type_instructions(voice_type)}



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
        Generate {count} {voice_type} lines for a prank call in {language} language. Return ONLY the spoken lines — no quotation marks, numbers, or bullets.

        Scenario: {title}
        Description: {description}
        Target Name: {target_name}

        Create {count} DIFFERENT Voice Line Texts.
    """

    if voice_type == "FILLER":
        temp = 0.3
    elif voice_type in ["OPENING", "CLOSING"]:
        temp = 0.7
    elif voice_type == "QUESTION":
        temp = 0.8
    else:
        temp = 0.9
    llm = ChatOpenAI(
        model="gpt-4.1-mini",
        temperature=temp,
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
            "language": state.language,
        })
        
        lines = result.lines        
        unique_lines = []
        seen_lower = set()
        for _ln in lines:
            _low = _ln.lower()
            if _low in seen_lower:
                continue
            seen_lower.add(_low)
            unique_lines.append(_ln)

        lines = unique_lines

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
