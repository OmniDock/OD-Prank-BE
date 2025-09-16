"""
Refine node - Extracts and refines scenario description from chat messages
"""
from typing import Dict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.state import DesignChatState
from app.core.logging import console_logger


async def refine_description_node(state: DesignChatState) -> Dict:
    """
    Refines the clarified scenario text based on chat messages
    """
    console_logger.info("Running refine description node")
    
    # If no messages, return current state
    if not state.messages:
        return {
            "scenario": state.scenario
        }
    
    system_prompt = """

        <Setup>
            You are a helpful assistant that summarizes the chat messages into a short, cohesive description of a prank-call scenario. 
            The description will be used to generate voice lines. Newer messages should update the description.
        </Setup>

        <Rules>
            - Use BOTH the assistant questions and the user answers as context. Treat user replies as answers to the most recent assistant question.
            - Start from the current description and MERGE in new facts from the chat. Preserve correct existing details; update only when the user changes them.
            - Do never invent details. If ambiguous, state that it is not clear. Our next LLM Request will ask for the details.
            - Include, when available:
              • Caller persona/role (e.g., DHL driver) and attitude/tone if implied
              • Callee personalization choice (generic vs name) and the name if provided
              • Small realism details (e.g., item specifics, address hint, tiny plausible cues)
              • Any safety-relevant constraints or boundaries
              • Any other details that are not clear or ambiguous.
            - Avoid low-impact timing questions. Infer simple delivery timing only if clearly implied; otherwise omit.
            - Write a single cohesive paragraph, declarative, with no questions. Just state the facts.
            - Refer to the callee in third person; the caller is described as a role the user plays (e.g., "als DHL-Fahrer").
            - Do NOT contradict the user's statements. Do NOT add speculative content.
            - In the Summary also place the language the user want to hear. If the user does not specify anything use the language of his messages. 
        </Rules>

    """
    
    user_prompt = """
        Last Chat Messages so far:
        {messages_text}
        
        Current summary (if any): {current_description}
        
        Write a short, cohesive scenario description (single paragraph).
        If there is already a description, update it with the new information.
    """
    
    # Format recent messages for prompt (include both assistant and user to link Q->A)
    recent = state.messages[-12:] if len(state.messages) > 12 else state.messages
    nonempty = [m for m in recent if (m.get('content') or '').strip()]
    if not nonempty and not (state.scenario or "").strip():
        console_logger.info("No content to refine yet; keeping description unchanged")
        return {"scenario": state.scenario}
    messages_text = "\n".join([
        f"{m.get('role','').upper()}: {m.get('content','').strip()}" for m in nonempty
    ])
    
    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.3)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({
            "messages_text": messages_text,
            "current_description": state.scenario or "No description yet"
        })
        
        content = (result.content or "").strip()
        # Safety: do not invent details; if model returns extremely generic content without user anchors, keep previous
        if not content:
            return {"scenario": state.scenario}
        console_logger.info(f"Refined description: {content[:100]}...")
        return {
            "scenario": content
        }
        
    except Exception as e:
        console_logger.error(f"Refine description failed: {str(e)}")
        return {
            "scenario": state.scenario
        }