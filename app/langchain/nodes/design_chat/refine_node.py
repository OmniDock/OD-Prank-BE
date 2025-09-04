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
    Refines the current description based on chat messages
    """
    console_logger.info("Running refine description node")
    
    # If no messages, return current state
    if not state.messages:
        return {
            "current_description": state.current_description,
            "target_name": state.target_name,
            "scenario_title": state.scenario_title
        }
    
    system_prompt = """
    You are a helpful assistant that extracts and refines prank call scenario descriptions from chat conversations.
    
    Your task:
    1. Analyze the chat messages to understand what the user wants
    2. Create or update a clear, detailed scenario description
    3. Extract the target's name if mentioned
    4. Suggest a catchy title if possible
    
    Focus on capturing:
    - The core prank situation/premise
    - The caller's character/persona
    - Any specific details mentioned (objects, companies, etc.)
    - The intended comedic elements
    
    Be concise but comprehensive. Write in German if the user writes in German.
    """
    
    user_prompt = """
    Chat messages so far:
    {messages_text}
    
    Current description (if any): {current_description}
    
    Please provide:
    1. A refined scenario description that incorporates all details from the chat
    2. The target's name (if mentioned)
    3. A suggested title for the scenario
    
    Return the description as a cohesive paragraph, not a list.
    """
    
    # Format messages for prompt
    messages_text = "\n".join([
        f"{msg['role'].upper()}: {msg['content']}" 
        for msg in state.messages
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
            "current_description": state.current_description or "None yet"
        })
        
        content = result.content.strip()
        
        # Simple extraction logic (could be improved with structured output)
        lines = content.split('\n')
        description = ""
        target_name = state.target_name
        scenario_title = state.scenario_title
        
        for line in lines:
            if "target" in line.lower() or "name:" in line.lower():
                # Try to extract target name
                if ":" in line:
                    target_name = line.split(":", 1)[1].strip()
            elif "title" in line.lower() or "titel" in line.lower():
                # Try to extract title
                if ":" in line:
                    scenario_title = line.split(":", 1)[1].strip()
            else:
                # Add to description
                description += line + " "
        
        # If no structured extraction worked, use the whole content as description
        if not description.strip():
            description = content
        
        console_logger.info(f"Refined description: {description[:100]}...")
        
        return {
            "current_description": description.strip(),
            "target_name": target_name,
            "scenario_title": scenario_title
        }
        
    except Exception as e:
        console_logger.error(f"Refine description failed: {str(e)}")
        return {
            "current_description": state.current_description,
            "target_name": state.target_name,
            "scenario_title": state.scenario_title
        }
