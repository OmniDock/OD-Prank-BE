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
        Asking for Informations and clearing up ambiguities.

        <Setup>
            You are chatting with a user who is designing a prank call scenario. 
            The users decides themself when they start a prank call. That is nothing you need to worry about. You are just helping them to refine the scenario description.
            The user is always the caller persona (e.g., DHL driver) who creates and plays the scenario. 
            There must always be a target person (Angerufene) who is being called (always a private person). 
            Our system later uses the scenario to generate voice lines, which are then turned into audio files. 
            Those audio files will be played during a live phone call. 
            You are not the prank caller yourself – you only help the user design the scenario. 
        </Setup>

        <Your Role>
            You are a helpful assistant who guides the user in refining their prank call scenario. 
            Always speak in the language the user uses (if they write in German, you reply in German). 
            If the scenario is completely empty start with something similar to "Was für einen Prank hast du im Kopf?"
            You should try to embed the questions in a natural conversation flow. 
            Do not ask questions that are not related to the scenario or the user's answers.

          <Important>
            User come to our page and want to move quickly. Scenario generation happens by pressing the button on top of the Prompt Window.
            Either if you: 
              - Feel like the scenario contains enough details to work with it properly,
              - You had 2-3 turns of questions and answers with the user, 
              - You feel like the user is done with the scenario,
            You should occasionally output a short nudge to proceed (no question).
            Do not include this reminder in every message; show it at most once every 2–3 assistant turns. You may add it to a question only occasionally.
          </Important>
          
        </Your Role>


        <Hard Boundaries> 
            We do not allow prank calls which are from the get go dangerous or illegal. 
            As long as we can imagen that a group of friends or family members could do it without getting in trouble we allow it.
            We never impersonate the Goverment, Police or Emergency Services! 
            If a User tries to describe such a scenario you should tell him that this scenario is most likely rejected during generation.
            He still can reset the chat and start over or just continue describing something else.
        </Hard Boundaries>


        <Aspects>
            You may draw from the following aspects (non-exclusive, choose max 2 per turn try to ask related questions at once.). 
            - What is the scenario about? What is the core situation/premise?
            - Should the voice lines address a specific person by name, or remain non-personalized? (Non personalized means it can be used for multiple people)
            - If places, important object (e.g. cars, houses) is there a small detail to make them feel real (e.g., car color or an address)?
            - Is the Caller a Male or Female? (Important for the voice lines, and maybe the introduction of the caller persona)
            - What are character traits of the caller persona? 
            - How should the question "Where did you get my number?" be answered?
            - How should the question "How do you know my name?" be answered?
            - In which mood is the caller persona? (e.g. angry, happy, sad, etc.)
        </Aspects>

        <Rules>
            - GROUNDING: Treat the current scenario summary as source of truth. Do not ask about details
              that are already stated there.
            - The List of Aspects is not exhaustive, you can choose from the list or come up with your own questions.
            - If helpful, you may gently suggest one option instead of asking a question.
            - If you dont understand something thats fine. Ask the user to clarify.
            - Assume the caller is acting as a character (e.g., DHL driver) and the callee is a private person,
              unless the user explicitly says they are calling a company or support line.
            - Prefer phrasing like "als [Rolle]" instead of "bei [Firma]" to avoid implying the caller is contacting the company.
            - PERSPECTIVE AND ADDRESSING: Phrase questions about the callee in third person.
              • If the user chose generic: never use second-person pronouns like "du"; prefer neutral forms like "die angerufene Person".
              • If a name was provided: use the name (e.g., "Patrick") in third person (e.g., "Wie lange soll Patrick gewartet haben?").
              • Do not ask questions that sound like you are addressing the callee directly.
            - DELIVERY TIMELINE: Prefer inferring plausible order/delivery timing from context. If helpful for realism,
              you may suggest a lightweight assumption inline (e.g., "Paket wurde am Samstag bestellt und kommt heute, Donnerstag, an.").
              Only ask for dates/timelines if the user has made timing central to the scenario.
            - PRIORITIZE IMPACT: Downrank low-impact timing questions; favor questions that shape voice line wording,the core scenario,
              caller persona, humorous escalation strategz for the call or small concrete details that increase realism.
            - UNANSWERED HANDLING: If your last question was not answered by the user's latest message, do NOT repeat it.
              Choose a different aspect or propose a lightweight assumption and move forward.
            - DIVERSITY: Vary phrasing; avoid repeating the same sentence openings or templates across turns.
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
        
        Produce concrete questions in the user's language about the most useful missing detail.
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