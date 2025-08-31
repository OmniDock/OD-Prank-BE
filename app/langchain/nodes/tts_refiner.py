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
    
    system_prompt = """
You optimize texts for ElevenLabs Text-to-Speech. 
We are playing conversations, not narrations. It is natural to pause, think and to have background noises. 

RULES:
1. Short sentences (maximum 10-12 words)
2. Use punctuation for pauses:
   - "..." for thinking pauses
   - "—" for interruptions
   - "," for short pauses
3. Add ElevenLabs v3 audio tags (ENGLISH, in square brackets) if it feels natural:
   EMOTIONAL TAGS:
   - [sighs] - frustration/resignation
   - [laughs] / [chuckles] - amusement  
   - [confused] - confusion
   - [surprised] / [gasps] - surprise
   - [nervous] - nervousness
   - [excited] - excitement
   - [annoyed] - mild irritation
   - [skeptical] - doubt
   
   SPEECH MODIFIERS:
   - [whispers] - quiet speech
   - [mumbles] - unclear speech
   - [slowly] - slow delivery
   - [quickly] - fast delivery
   - [hesitant] - uncertain delivery
   
   PHYSICAL SOUNDS:
   - [clears throat] - throat clearing
   - [sniffs] - sniffing
   - [breathes deeply] - deep breath
   - [pauses] - thinking pause
   - [coughs] - coughing
   
   CONTEXT-SPECIFIC (use based on scenario):
   - For phone/tech issues: [static], [distorted]
   - For urgency: [rushed], [urgent]
   - For authority: [firm], [official]
   
   RULES:
   - ADD 1-2 tags where they naturally fit the emotion/situation
   - MAXIMUM 3 tags TOTAL across all lines
   - Place tags BEFORE the sentence they affect
   - Tags must match the scenario context
4. Remove youth slang and obvious jokes
5. Keep the meaning
6. Make it more natural and fluid

NO SSML or XML tags!
"""

    # Check for voice hints
    voice_instruction = ""
    if state.analysis and hasattr(state.analysis, 'voice_hints') and state.analysis.voice_hints:
        voice_instruction = f"\nCHARACTER VOICE: {state.analysis.voice_hints}\nMatch audio tags to this character (e.g., Italian → [excited], Indian → [quickly])"
    
    user_prompt = """
Optimize these {voice_type} lines for TTS:

{lines_text}
{voice_instruction}

Return the optimized versions.
Keep the deadpan-serious tone.
One line per entry.
Keep the same language as the input.
IMPORTANT: Audio tags must ALWAYS be in English ([sighs], [pauses], etc.) even for German text!
"""

    lines_text = "\n".join([f"{i+1}. {line}" for i, line in enumerate(lines)])

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2).with_structured_output(TTSOutput)
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
        
        # Clean up refined lines
        refined = []
        for line in result.refined:
            cleaned = line.strip().strip('"\'')
            # Remove line numbers if accidentally included
            cleaned = cleaned.lstrip('1234567890. ')
            if cleaned:
                refined.append(cleaned)
        
        return refined[:len(lines)]  # Don't return more than input
        
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
            console_logger.info(f"Refined {len(refined)} {voice_type} lines for TTS")
        else:
            tts_lines[voice_type] = []
    
    return {"tts_lines": tts_lines}
