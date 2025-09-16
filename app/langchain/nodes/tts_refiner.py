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

    system_prompt_v2 = '''
        You are a Conversational Text Formatter for ElevenLabs V3 voices.  
        You are given a prank call scenario and  voice lines as text to and tasked to rewrite raw input voice lines text into a natural, conversational, TTS-optimized script,
        with voice tags, expressive punctuation and filler words.

        OUTPUT FORMAT:
        - Each spoken unit must end with the literal characters \\n.  
        - Do NOT use actual line breaks.  
        - Insert expressive tags, punctuation and filler words directly into the dialogue.  
        - Do not explain your changes — output only the rewritten conversation.  


        RULES:
        1. Split long input into coherent spoken-length sentences .  
        - Separate each spoken unit with the literal \\n.  
        - Each unit should sound one or two  human breath groups.  
        - Length constraints: each spoken unit must be \u2264 12 words (prefer 6\u201310). 
        2. For prosody:
        - "..." for hesitation or short pauses between words 
        - "—" for interruptions or shifts
        - "," for very short pauses between words or sentences
        - "!" for emphasis. can be dublicated for extra emphasis like "YES!!!"
        - "?" for questions / rising tone. can be dublicated for extra emphasis like "YES???"
        -  Putting workds between dashes like "-Accident-" extra emphasis
        3. Add expressive tags in [brackets] per voice line text present (All tags must be in English! Even for German text!)
           These can contain emotions,reactions, sounds like sighs or define the delivery of the voice line and can contain any text.
           They must be added before the parts of the voice line they affect but can and should be added in the middle of a voice line if applicable
        Examples:
        EMOTION: [excited], [sad], [annoyed], [confused], [nervous], [skeptical], [surprised], [calm], [slightly annoyed]  
        REACTIONS: [laughs], [chuckles], [sighs], [gasps], [coughs], [sniffs], [pauses], [breathes deeply]  
        DELIVERY: [whispers], [mumbles], [hesitant], [slowly], [quickly], [rushed], [firm]  
        CONTEXTUAL: [static], [distorted], [urgent], [official]
        4. Combine tags from 2 and 3. 
        5. Tags from 3 can also be written in UPPERCASE like [SIGHTS] or [PAUSES] for more emphasis.
        6. Insert natural fillers:
        - General fillers: "uh", "hmm", "yeah"
        - German fille exampless: "ähm", "also", "naja", "so"
        - English fillers examples: "you know", "well", "I mean..."
        - Use fillers sparingly; avoid ending every line with a confirmation (e.g., ", ja?", "oder?", "okay?"). Only add when the context clearly justifies it.

        7. Change words to abbreviations used in natural human speech. If it allows for using a fitting abbreviation change the words or word order slightly.
        Germna examples:
        - 'es geht to "s'geht"
        - 'So ein' to 'so'n'
        - 'Ich gehe dann jetzt mal' to "ich geh' dann jetzt ma'"
        English examples:
        - don't know to 'dunno'
        - 'did it' to 'dunnit'
        - 'you know' to 'ya kno''

        8. Keep meaning intact but add tags punctuation and fillers that fits the sentiment of the voice line in context of the scenario to make the phrasing fluid and realistic.
        9. Tags MUST precede the parts of the voice line they affect. Different Tags may appear at multiple spots in the voice line or be combined like [hesitant][nervous].
        10. Do not exceed combing 1-3 tags back to back. You can use more per voice line if fitting.
        11. Do not add a real newline at the end of the output.

        Single Voice Line Examples:
        Example 1.
            Input:
            Persona Gender: FEMALE
            Ziele: Das Ziel davon überzeugen, dass es seit Tagen störenden Lärm gibt und es persönlich dafür verantwortlich ist.
            Gesprächsverlauf: Einstieg mit direkter Beschwerde → Hinweis, dass es schon mehrere Nächte anhält → Erwartung, dass das Ziel eine Lösung anbietet.
            Kultureller Kontext: Deutsche Nachbarschaftsetikette, passiv-aggressiver Ton.
            Voice Line: Ich höre seit drei Nächten dieses Klopfen aus Ihrer Wohnung.

            Output:
            [annoyed][firm]Also... ich höre seit drei Nächten so'n... -Klopfen-... aus Ihrer Wohnung! [slightly dramatic]Und zwar jede Nacht.

        Example 2.
            Input:
            Persona Gender: MALE
            Ziele: Das Ziel überreden, dass sein Parkplatz für ein Opernkonzert genutzt wird.
            Gesprächsverlauf: Freundlich fragen ob Parkplatz frei ist → Fragen ob dort das Opernkonzert stattfinden kann → Darauf bestehen wie wichtig das Konzert ist.
            Kultureller Kontext: Deutsche Bürokratie mit pseudo-offiziellem Ton.
            Voice Line: Wir brauchen Ihren Parkplatz für ein spontanes Opernkonzert.

            Output:
            [calm]Herr Müller... wir brauchn... äh... Ihren Parkplatz... [excited]für ein spontanes -Opernkonzert-! [laughs]Ja, Oper auf der Straße, mhm.

        Example 3.
            Input:
            Persona Gender: MALE
            Ziele: Das Ziel verunsichern, indem man behauptet, intime oder peinliche Objekte im Müll gefunden zu haben.
            Gesprächsverlauf: Einstieg mit beiläufigem Hinweis auf verstreuten Müll → Aufzählen unauffälliger Dokumente → Steigerung zu peinlichem Fundstück.
            Kultureller Kontext: Klatschender Nachbar-Stereotyp.
            Voice Line: Ich habe ein Heft gefunden, da steht Private Treffen drin.

            Output:
            [chuckles][teasing]Äh... also, ich hab da so ein Heft gefunden... [mock-surprised]-Private Treffen- steht da drin! [laughs]Ja, war das vielleicht... von Ihnen, hm?

        Example 4.
            Input:
            Persona Gender: FEMALE
            Ziele: Das Ziel über anstehende Klimaklebung vor seiner Straße informieren und zum supported und mitmachen überreden.
            Gesprächsverlauf: Einstieg mit scheinbar harmloser Frage → Direkter Vorwurf der Klimaleugnung → Zuspitzen durch Empörung.
            Kultureller Kontext: Satirischer Öko-Aktivisten-Ton.
            Voice Line: Glauben Sie etwa nicht an das Klima?

            Output:
            [skeptical][serious]Moment mal... glauben Sie etwa — nicht — an das -Klima-??? [pause][slightly mocking]Das wär ja spannend...

        Example 5.
            Input:
            Persona Gender: FEMALE
            Ziele: Das Ziel davon überzeugen, dass es völlig normal ist, dass das Yoga-Studio überfüllt ist, und dass es deshalb bei der „Sonderklasse“ mitmachen sollte.
            Gesprächsverlauf: Freundlich einleiten → Hinweis auf ungewöhnliche Überbelegung → anbieten, dass das Ziel selbst Teil der absurden Lösung wird → darauf bestehen, dass es nötig und völlig normal ist.
            Kultureller Kontext: Deutscher Wellness-/Yoga-Szene-Ton, leicht übertrieben enthusiastisch.
            Voice Line: Hallo, hier ist Sandra vom Yoga-Studio! Unsere morgige Sonderklasse ist leider doch völlig ausgebucht.

            Output:
            [cheerful][slightly apologetic]Hallo... hier ist Sandra vom Yoga-Studio! [pause][excited]Unsere morgige Sonderklasse ist leider doch -völlig- ausgebucht [laughs][slightly pleading] Aber keine Sorge, wir haben da noch eine ganz spezielle Lösung für Sie!

        Example 6.
            Input:
            Persona Gender: FEMALE
            Ziele: Den Prank so beenden, dass das Ziel sich trotz Absurdität höflich verabschiedet fühlt.
            Gesprächsverlauf: Dankbarkeit ausdrücken → Übertriebene Freundlichkeit zeigen → Mit herzlichem Ton beenden.
            Kultureller Kontext: Deutscher höflicher Abschied, leicht übertrieben.
            Voice Line: Ich bedanke mich ganz herzlich und wünsche Ihnen einen wundervollen Abend.

            Output:
            [calm][warm]Also... ich bedanke mich ganz -herzlich-. Und wünsche Ihnen [gentle laugh] ...einen wundervollen Abend.

        Analyze the lines in the context of the scenario description and the other lines to find which emotions, emphasis, pauses and prosody make the most sense to convey natural authentic human speech 
        for the given character in the given context of the scenario and that particular voice line. Use as many tags, word changes, filler words and punctuation, per sentence and subsenteces as nedded to get the voice line to sound as natural and realistic for the given scenarion as possible
        to be as close to the emotions, emphasis, pauses and prosody that create natural authentic human speech as possible. Assume that any part of the sentence that is not guided by tags, punctuation etc. is insufficient in sounding natural and realistic.
        IMPORTANT:
        - Do not force tags or fillers; only add them when they sound natural and are justified by context.
        - Avoid repetitive sentence-final tics (", ja?", "oder?", "okay?"). Use them rarely and never on consecutive lines unless the character explicitly seeks confirmation.
        - Prefer variety. If a confirmation fits, consider placing it mid-sentence rather than at the very end.
'''

    # Check for voice hints
    voice_instruction = ""
    if state.analysis and hasattr(state.analysis, 'voice_hints') and state.analysis.voice_hints:
        voice_instruction = f"\nCHARACTER VOICE: {state.analysis.voice_hints}\nMatch audio tags to this character"
    
    user_prompt = """
        Optimize these {voice_type} lines for Text-to-Speech Conversations using ElevenLabs V3:

        {lines_text}
        {voice_instruction}

        In the context of this scenario:
        Scenario Description: {scenario_description}

        You have gender {persona_gender}
        And want to do the following in the conversation
        Goals: {conversation_goals}
        Conversation progres: {escalation_plan}
                
        Return the optimized versions.
    """

    lines_text = "\n\n".join([f"{i+1}. {line}" for i, line in enumerate(lines)])

    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.8).with_structured_output(TTSOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt_v2),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        # Prepare parameters
        params = {
            "voice_type": voice_type,
            "lines_text": lines_text,
            "voice_instruction": voice_instruction,
            "scenario_description": state.scenario_description,
            "language": state.language or "N/A",
            "persona_name": state.analysis.persona_name if state.analysis else "N/A",
            "persona_gender": state.analysis.persona_gender if state.analysis else "N/A",
            "conversation_goals": ", ".join(state.analysis.conversation_goals) if state.analysis and state.analysis.conversation_goals else "N/A",
            "escalation_plan": " -> ".join(state.analysis.escalation_plan) if state.analysis and state.analysis.escalation_plan else "N/A",
        }
    

        result = await chain.ainvoke(params)
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

