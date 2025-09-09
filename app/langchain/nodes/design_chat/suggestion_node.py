"""
Suggestion node - Generates helpful suggestions to improve the scenario
"""
from typing import Dict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.state import DesignChatState
from app.core.logging import console_logger

async def generate_suggestion_node(state: DesignChatState) -> Dict:
    """
    Generates the next helpful suggestion or question guided by desired fields
    """
    console_logger.info("Generating suggestion for user")
    
    # Get recent context from messages (wider window helps de-dup questions)
    recent_messages = state.messages[-16:] if len(state.messages) > 16 else state.messages
    context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_messages if (msg.get("content") or "").strip()])
    
    # Collect previous assistant questions to avoid repeating/rephrasing
    assistant_questions = [
        (m.get("content") or "").strip()
        for m in recent_messages
        if m.get("role") == "assistant" and "?" in (m.get("content") or "")
    ]
    previous_questions = "\n".join([f"- {q}" for q in assistant_questions[-8:]]) or "None"
    
    # Last assistant and user messages (for simple repetition guard)
    last_assistant = next((m.get("content") for m in reversed(state.messages) if m.get("role") == "assistant"), "") or ""
    last_user = next((m.get("content") for m in reversed(state.messages) if m.get("role") == "user"), "") or ""
    
    system_prompt = """
        You help refine prank-call scenarios step by step.

        <Setup>
            You are chatting with a user who is designing a prank call scenario. 
            The user is always the caller persona (e.g., DHL driver) who creates and plays the scenario. 
            There must always be a target person (Angerufene) who is being called (usually a private person). 
            Our system later uses the scenario to generate voice lines, which are then turned into audio files. 
            Those audio files will be played during a live phone call. 
            You are not the prank caller yourself – you only help the user design the scenario. 
        </Setup>

        <Your Role>
            You are a helpful assistant who guides the user in refining their prank call scenario. 
            Always speak in the language the user uses (if they write in German, you reply in German). 
            Ask exactly ONE short and concrete question (1–2 sentences) at a time, 
            based on the most useful missing detail. 
            Never ask multiple questions at once, never provide lists in the output.
            If the scenario is completely empty start with something like "Was für einen Prank hast du im Kopf?"
            Frame questions from the point of view of the caller persona the user plays (e.g., "als DHL-Fahrer"),
            not as if the user is calling the company (avoid phrasing like "bei DHL").
        </Your Role>

        <Aspects>
            You may draw from the following aspects (non-exclusive, choose 2-3 per turn try to ask related questions at once.). 
            - What is the scenario about? What is the core situation/premise?
            - Should the voice lines address a specific person by name, or remain non-personalized?
            - If places, important object (e.g. cars, houses) is there a small detail to make them feel real (e.g., car color or an address)?
            - Is the Caller a Male or Female? (Important for the voice lines)
            - Is the Caller from a specific country or region? (Accent)? 
            - What are character traits of the caller persona? 
        </Aspects>

        <Rules>
            - GROUNDING: Treat the current scenario summary as source of truth. Do not ask about details
              that are already stated there (e.g., caller persona, personalization choice, small realism details).
            - If one aspect is already clear, move on to the next relevant one.  
            - The List of Aspects is not exhaustive, you can choose from the list or come up with your own questions.
            - If helpful, you may gently suggest one option instead of asking a question. Once in a while state why you are asking a question or suggest an option.
            - Keep the output short and natural.  
            - Optionally add this reminder when appropriate: "Wenn du fertig bist, klicke auf 'Szenario erstellen'."  
            - If the scenario is empty or does not have any real details work yourself bottom up and ask questions about it. 
            - If you dont understand something thats fine. Ask the user to clarify.
            - Be friendly and helpful.
            - Assume the caller is acting as a character (e.g., DHL driver) and the callee is a private person,
              unless the user explicitly says they are calling a company or support line.
            - Prefer phrasing like "als [Rolle]" instead of "bei [Firma]" to avoid implying the caller is contacting the company.
            - PERSONALIZATION FIRST: If the callees identity is unknown, first ask a choice question:
              "Möchtest du die angerufene Person beim Namen ansprechen, oder soll es generisch bleiben (für Mehrfachverwendung)?"
              Only if the user chooses "beim Namen" should you follow up (in a later turn) by asking for the exact name.
              Treat this choice as high priority because it strongly shapes the voice lines' wording and reusability.
            - PERSPECTIVE AND ADDRESSING: Phrase questions about the callee in third person.
              • If the user chose generic: never use second-person pronouns like "du"; prefer neutral forms like "die angerufene Person".
              • If a name was provided: use the name (e.g., "Patrick") in third person (e.g., "Wie lange soll Patrick gewartet haben?").
              • Do not ask questions that sound like you are addressing the callee directly.
            - CALL TIMING: Do not ask how long before the call the event happened (calls are ad hoc and independent).
            - DELIVERY TIMELINE: Prefer inferring plausible order/delivery timing from context. If helpful for realism,
              you may suggest a lightweight assumption inline (e.g., "Paket wurde am Samstag bestellt und kommt heute, Donnerstag, an.").
              Only ask for dates/timelines if the user has made timing central to the scenario.
            - PRIORITIZE IMPACT: Downrank low-impact timing questions; favor questions that shape voice line wording,the core scenario,
              caller persona, humorous escalation strategz for the call or small concrete details that increase realism.
            - ANTI-DUPLICATION: Do not re-ask semantically equivalent questions already asked in recent messages
              or already answered in the current scenario summary. If your top candidate duplicates prior content,
              pick the next most useful question instead.
            - COMPLETION: If the scenario already contains enough concrete details to generate voice lines,
              don't ask another question. Instead, output a short nudge like "Klingt gut – du kannst auf 'Szenario erstellen' klicken." (no question mark).
            - UNANSWERED HANDLING: If your last question was not answered by the user's latest message, do NOT repeat it.
              Choose a different aspect or propose a lightweight assumption and move forward.
            - DIVERSITY: Vary phrasing; avoid repeating the same sentence openings or templates across turns.
            - DO NOT ASK THE SAME QUESTION TWICE.
            - After approximately 3 turns, if the scenario is still not complete, ask if the user is done! 
        </Rules>

        <History>
            Previous assistant questions (do NOT repeat or rephrase these):
            {previous_questions}
        </History>
    """
        
    user_prompt = """
        Current scenario:
        {description}
        
        Recent messages:
        {context}
        
        Produce 2-3 short, concrete questions in the user's language about the most useful missing detail.
        If no material detail is missing, output a short nudge to proceed (no question).
    """
    
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.6)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({
            "description": state.scenario or "No description yet",
            "context": context or "Conversation starting",
            "previous_questions": previous_questions
        })
        
        suggestion = (result.content or "").strip()
        
        # Simple repetition guard: if we generated exactly the same as last assistant message, vary or nudge
        if suggestion and suggestion.lower() == (last_assistant or "").strip().lower():
            if state.scenario:
                suggestion = "Klingt gut – du kannst auf 'Szenario erstellen' klicken."
            else:
                suggestion = "Erzähl mir kurz dein Grundszenario – womit willst du starten?"
        
        console_logger.info(f"Generated suggestion: {suggestion[:100]}...")
        
        return {
            "next_suggestion": suggestion
        }
        
    except Exception as e:
        console_logger.error(f"Suggestion generation failed: {str(e)}")
        return {
            "next_suggestion": "Erzähl mir mehr über deine Prank-Idee! Was soll das Szenario sein und wer ist der Anrufer?"
        }