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
            "clarified_scenario": state.clarified_scenario
        }
    
    system_prompt = """
        You extract the prank idea from the chat and write a short, clear description.
        Focus: situation/premise, caller role, relevant details, tone.
    """
    
    user_prompt = """
        Chat so far:
        {messages_text}
        
        Current summary (if any): {current_description}
        
        Write a short, cohesive scenario description (single paragraph, in German).
    """
    
    # Format messages for prompt (use ONLY user messages to avoid model seeding from assistant turns)
    user_messages = [m for m in state.messages if m.get('role') == 'user']
    contents = [m.get('content', '').strip() for m in user_messages if m.get('content')]
    # Require at least one meaningful user message (length and some structure)
    has_meaningful = any(len(c) >= 15 and c.count(' ') >= 2 for c in contents)
    if not has_meaningful:
        console_logger.info("Not enough meaningful user content yet to refine scenario")
        return {"scenario": ""}
    messages_text = "\n".join([
        f"USER: {m.get('content','')}"
        for m in user_messages
    ])
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
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
