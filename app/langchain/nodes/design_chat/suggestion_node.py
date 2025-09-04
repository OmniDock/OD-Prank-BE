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
    Generates the next helpful suggestion or question based on what's missing
    """
    console_logger.info("Generating suggestion for user")
    
    # Format missing aspects for the prompt
    missing_text = "\n".join([f"- {aspect}" for aspect in state.missing_aspects]) if state.missing_aspects else "General improvement needed"
    
    # Get recent context from messages
    recent_messages = state.messages[-3:] if len(state.messages) > 3 else state.messages
    context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_messages])
    
    system_prompt = """
    Du bist ein freundlicher, kreativer Assistent, der jemandem hilft, ein lustiges Prank-Call-Szenario zu entwickeln.
    
    Deine Rolle:
    - Sei ZURÜCKHALTEND mit Vorschlägen - lass den User die Kreativität zeigen
    - Stelle nur EINE gezielte Frage zu fehlenden Details
    - Keine langen Erklärungen oder mehrere Vorschläge
    - Bestätige kurz was gut ist, dann frage nach dem Nächsten
    - Maximal 1-2 Sätze pro Antwort
    
    Fokus auf Pranks die:
    - Glaubwürdig aber absurd sind
    - Harmlos und spielerisch
    - Natürlich eskalieren
    
    WICHTIG: Antworte IMMER auf Deutsch, außer der User schreibt explizit auf Englisch.
    WICHTIG: Sei NICHT zu proaktiv - lass den User führen!
    """
    
    user_prompt = """
    Current scenario: {description}
    
    Missing aspects:
    {missing}
    
    Recent conversation:
    {context}
    
    Generate ONE short question to get the missing information from the user.
    Don't suggest ideas - just ask what they have in mind.
    Keep it very brief and conversational.
    """
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({
            "description": state.current_description or "No scenario described yet",
            "missing": missing_text,
            "context": context or "Starting fresh"
        })
        
        suggestion = result.content.strip()
        
        # Add some variety with follow-up prompts
        if not state.current_description:
            suggestion = "Was für einen Prank hast du im Kopf?"
        elif len(state.messages) == 1:
            suggestion = f"Okay! {suggestion}"
        
        console_logger.info(f"Generated suggestion: {suggestion[:100]}...")
        
        return {
            "next_suggestion": suggestion
        }
        
    except Exception as e:
        console_logger.error(f"Suggestion generation failed: {str(e)}")
        # Fallback suggestion
        return {
            "next_suggestion": "Erzähl mir mehr über deine Prank-Idee! Was soll das Szenario sein und wer ist der Anrufer?"
        }
