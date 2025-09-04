"""
TTS Refiner node - optimizes lines for text-to-speech
"""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.state import ScenarioState
from app.core.logging import console_logger


class TTSOutput(BaseModel):
    """Structured output for TTS refinement"""
    refined: List[str] = Field(description="TTS-optimized lines")


async def refine_lines(lines: List[str], voice_type: str, state: Optional[ScenarioState] = None) -> List[str]:
    """Refine lines for optimal TTS delivery"""
    
    if not lines:
        return []
    
    # system_prompt = """
    #     You optimize texts for ElevenLabs Text-to-Speech. 
    #     We are playing conversations, not narrations. It is natural to pause, think and to have background noises. 

    #     RULES:
    #     1. Short sentences (maximum 10-12 words)
    #     2. Use punctuation for pauses:
    #     - "..." for thinking pauses
    #     - "—" for interruptions
    #     - "," for short pauses
    #     3. Add ElevenLabs v3 audio tags (ENGLISH, in square brackets) if it feels natural:
    #     EMOTIONAL TAGS:
    #     - [sighs] - frustration/resignation
    #     - [laughs] / [chuckles] - amusement  
    #     - [confused] - confusion
    #     - [surprised] / [gasps] - surprise
    #     - [nervous] - nervousness
    #     - [excited] - excitement
    #     - [annoyed] - mild irritation
    #     - [skeptical] - doubt
        
    #     SPEECH MODIFIERS:
    #     - [whispers] - quiet speech
    #     - [mumbles] - unclear speech
    #     - [slowly] - slow delivery
    #     - [quickly] - fast delivery
    #     - [hesitant] - uncertain delivery
        
    #     PHYSICAL SOUNDS:
    #     - [clears throat] - throat clearing
    #     - [sniffs] - sniffing
    #     - [breathes deeply] - deep breath
    #     - [pauses] - thinking pause
    #     - [coughs] - coughing
        
    #     CONTEXT-SPECIFIC (use based on scenario):
    #     - For phone/tech issues: [static], [distorted]
    #     - For urgency: [rushed], [urgent]
    #     - For authority: [firm], [official]
        
    #     RULES:
    #     - ADD 1-2 tags where they naturally fit the emotion/situation
    #     - MAXIMUM 3 tags TOTAL across all lines
    #     - Place tags BEFORE the sentence they affect
    #     - Tags must match the scenario context
    #     4. Remove youth slang and obvious jokes
    #     5. Keep the meaning
    #     6. Make it more natural and fluid

    #     NO SSML or XML tags!
    # """

    system_prompt = """
        You are a Conversational Text Formatter for ElevenLabs V3 voices.  
        Your task: Rewrite raw input text into a natural, conversational, TTS-friendly script.

        OUTPUT FORMAT:
        - Wrap the entire final result inside <formatted> ... </formatted>.  
        - Each spoken unit must end with the literal characters \\n.  
        - Do NOT use actual line breaks.  
        - Insert expressive tags and punctuation directly into the dialogue.  
        - Do not explain your changes — output only the rewritten conversation.  

        RULES:
        1. Split long input into short spoken-length sentences (8–12 words max).  
        - Separate each spoken unit with the literal \\n.  
        - Each unit should sound like a single human breath group.  
        2. Use punctuation for prosody:
        - "..." for hesitation or long pause
        - "—" for interruptions or shifts
        - "," for short pauses
        - "!" for emphasis
        - "?" for questions / rising tone
        3. Add up to 1–3 expressive tags in [brackets] per voice line text presente (All tags must be in English! Even for German text!):
        EMOTION: [excited], [sad], [annoyed], [confused], [nervous], [skeptical], [surprised], [calm]  
        REACTIONS: [laughs], [chuckles], [sighs], [gasps], [coughs], [sniffs], [pauses], [breathes deeply]  
        DELIVERY: [whispers], [mumbles], [hesitant], [slowly], [quickly], [rushed], [firm]  
        CONTEXTUAL: [static], [distorted], [urgent], [official]
        4. Tags from 2 and 3 can be combined. 
        5. Tags from 3 can also be written in UPPERCASE like [SIGHTS] or [PAUSES] for more emphasis.
        6. Insert natural fillers where human (not narration) style is expected:
        - "uh", "hmm", "you know", "well", "I mean"
        - German fillers: "ähm", "also", "naja", "so", "vielleicht"
        7. Keep meaning intact but make phrasing fluid and realistic.
        8. Tags must precede the parts of the voice line they affect.  
        Tags may appear multiple times or be combined like [hesitant][nervous].
        9. Do not exceed 3 tags per voice line.
        10. Do not add a real newline at the end of the output.

        ---

        ### EXAMPLES

        **Example 1 – English, simple split**
        Input:  
        I think we should go to the park tomorrow if the weather is good. Otherwise maybe stay home and watch a movie.  

        Output:  
        [hmm] I think... we should go to the park tomorrow, if it’s nice.\\n  
        Otherwise—well, we could just stay home.\\n  
        [excited] Or! we could watch a movie.\\n  

        ---

        **Example 2 – English, multiple tags**  
        Input:  
        I just got the new phone and it works perfectly. The sound quality is very clear and I can even whisper.  

        Output:  
        [excited] I just got the new phone!\\n  
        The sound quality’s so clear...\\n  
        [whispers][playful] I can even whisper now.\\n  

        ---

        **Example 3 – German, fillers + hesitation**  
        Input:  
        Ich glaube, das Paket hätte eigentlich gestern ankommen sollen. Vielleicht war der Verkehr das Problem.  

        Output:  
        [hmm] Ich glaube... das Paket hätte gestern ankommen sollen.\\n  
        Vielleicht—also, war der Verkehr das Problem?\\n  

        ---

        **Example 4 – German, combined tags**  
        Input:  
        Könnten Sie mir vielleicht kurz helfen, weil ich unsicher bin?  

        Output:  
        [hesitant][NERVOUS] Ähm... könnten Sie mir vielleicht kurz helfen?\\n  
        [calm] Ich bin mir da nicht ganz sicher.\\n  

        ---

        **Example 5 – Mid-sentence tag placement**  
        Input:  
        Honestly I don’t know what to do right now.  

        Output:  
        Honestly—[sighs] I don’t know... what to do right now.\\n  

        ---

        **Example 6 – Polite closing**  
        Input:  
        Thanks again for your patience, I really appreciate it.  

        Output:  
        [POLITE] Thanks again for your patience.\\n  
        I really appreciate it.\\n  

        ---

        **Example 7 – German polite closing**  
        Input:  
        Vielen Dank für Ihre Geduld, es tut mir wirklich leid.  

        Output:  
        [polite] Vielen Dank für Ihre Geduld.\\n  
        Es tut mir wirklich leid.\\n  
        """

    # Check for voice hints
    voice_instruction = ""
    if state.analysis and hasattr(state.analysis, 'voice_hints') and state.analysis.voice_hints:
        voice_instruction = f"\nCHARACTER VOICE: {state.analysis.voice_hints}\nMatch audio tags to this character (e.g., Italian → [excited], Indian → [quickly])"
    
    user_prompt = """
        Optimize these {voice_type} lines for Text-to-Speech Conversations using ElevenLabs V3:

        {lines_text}
        {voice_instruction}

        Return the optimized versions.
    """

    lines_text = "\n\n".join([f"{i+1}. {line}" for i, line in enumerate(lines)])

    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.5).with_structured_output(TTSOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({
            "voice_type": voice_type,
            "lines_text": lines_text,
            "voice_instruction": voice_instruction
        })
        return result.refined[:len(lines)] 
        
    except Exception as e:
        console_logger.error(f"TTS refinement failed: {str(e)}")
        return lines  # Return original if refinement fails


async def tts_refiner_node(state: ScenarioState) -> dict:
    """
    Refine all plain lines for TTS
    """
    console_logger.info("Running TTS refiner node")
    
    tts_lines = {}
    
    for voice_type, lines in state.plain_lines.items():
        if lines:
            refined = await refine_lines(lines, voice_type, state)
            tts_lines[voice_type] = refined
            console_logger.debug(f"Refined {len(refined)} {voice_type} lines for TTS")
        else:
            tts_lines[voice_type] = []
    
    return {"tts_lines": tts_lines}
