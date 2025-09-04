"""
Readiness node - Checks if scenario has enough information to proceed
"""
from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.state import DesignChatState
from app.core.logging import console_logger


async def check_readiness_node(state: DesignChatState) -> Dict:
    """
    Checks if the scenario description has enough detail to generate a good prank
    """
    console_logger.info("Checking scenario readiness")
    
    # If no description yet, not ready
    if not state.current_description:
        console_logger.info("No description yet - not ready")
        return {
            "is_ready": False,
            "missing_aspects": [
                "Basic scenario description",
                "Caller character/persona", 
                "Target information"
            ]
        }
    
    system_prompt = """
    You are an expert comedy script writer evaluating if a prank call scenario has enough detail.
    
    NECESSARY ASPECTS for a good prank call:
    1. SCENARIO: A believable but funny core situation (e.g., wrong delivery, complaint, survey)
    2. CHARACTER: Clear caller persona with personality traits that fit the scenario
    3. TARGET: Basic info about who we're calling (name or role)
    4. COMEDY: Room for comedic escalation while staying believable
    5. DETAILS: If objects are important (car, package, etc.), they need basic details
    
    Evaluate the description and determine:
    - Is it ready to generate a full prank scenario? (true/false)
    - What aspects are missing or need more detail? (list them)
    
    Be encouraging but honest. We want quality pranks!
    """
    
    user_prompt = """
    Current scenario description:
    {description}
    
    Target name: {target_name}
    
    Please evaluate if this has enough detail to create a memorable prank call.
    
    Return:
    1. ready: true/false
    2. missing: list of missing aspects (empty list if ready)
    
    Be specific about what's missing, but don't be overly picky.
    """
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({
            "description": state.current_description,
            "target_name": state.target_name or "Not specified yet"
        })
        
        content = result.content.strip().lower()
        
        # Parse the response
        is_ready = False
        missing_aspects = []
        
        # Check for readiness indicators
        if "ready: true" in content or "is ready" in content or "genug detail" in content:
            is_ready = True
        elif "ready: false" in content or "not ready" in content or "nicht genug" in content:
            is_ready = False
        else:
            # Default check - if no clear missing aspects mentioned, assume ready
            is_ready = "missing:" not in content and "fehlt" not in content
        
        # Extract missing aspects
        if not is_ready:
            lines = result.content.split('\n')
            for line in lines:
                line = line.strip()
                if line and any(indicator in line.lower() for indicator in ['missing:', 'fehlt:', '-', '•', '*']):
                    # Clean up the line
                    aspect = line.lstrip('- •*').strip()
                    if aspect and len(aspect) > 3:  # Avoid empty or too short entries
                        # Remove "missing:" prefix if present
                        aspect = aspect.replace('missing:', '').replace('fehlt:', '').strip()
                        if aspect:
                            missing_aspects.append(aspect)
        
        # Fallback missing aspects if none extracted but marked not ready
        if not is_ready and not missing_aspects:
            missing_aspects = ["More detail about the scenario and character needed"]
        
        console_logger.info(f"Readiness check: ready={is_ready}, missing={len(missing_aspects)} aspects")
        
        return {
            "is_ready": is_ready,
            "missing_aspects": missing_aspects[:4]  # Limit to 4 aspects
        }
        
    except Exception as e:
        console_logger.error(f"Readiness check failed: {str(e)}")
        # On error, be conservative and ask for more info
        return {
            "is_ready": False,
            "missing_aspects": ["Could not evaluate - please provide more detail about your prank idea"]
        }
