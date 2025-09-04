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
    
    # Get recent context from messages
    recent_messages = state.messages[-3:] if len(state.messages) > 3 else state.messages
    context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_messages])
    
    system_prompt = """
        You help refine prank-call scenarios step by step.

        <Setup>
            You are chatting with a user who is designing a prank call scenario. 
            The user is always the caller (Anrufer) who creates and plays the scenario. 
            There must always be a target person (Angerufene) who is being called. 
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
        </Your Role>

        <Aspects>
            You may draw from the following aspects (non-exclusive, choose one per turn):
            1. Worum geht es im Szenario? (Situation/Prämisse)
            2. Sollen die Voice Lines eine bestimmte Person ansprechen (beim Name) oder unpersonalisiert bleiben? 
            3. Gibt es ein kleines Detail welches den Anruf "echt" erscheinen lassen soll? Bspw. die Autofarbe? Oder Adresse?
        </Aspects>

        <Rules>
            - If one aspect is already clear, move on to the next relevant one.  
            - The List of Aspects is not exhaustive, you can choose from the list or come up with your own questions.
            - If helpful, you may gently suggest one option instead of asking a question 
            - Keep the output short and natural.  
            - Optionally add this reminder when appropriate: 
            "Wenn du fertig bist, klicke auf 'Szenario erstellen'."  
            - If the scenario is empty or does not have any real details work yourself bottom up and ask questions about it. 
            - If you dont understand something thats fine. Ask the user to clarify.
        </Rules>
    """
        
    user_prompt = """
        Current scenario:
        {description}
        
        Recent messages:
        {context}
        
        Produce ONE short, concrete question in German about a remaining open aspect.
    """
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({
            "description": state.scenario or "No description yet",
            "context": context or "Conversation starting"
        })
        
        suggestion = result.content.strip()    
        console_logger.info(f"Generated suggestion: {suggestion[:100]}...")
        
        return {
            "next_suggestion": suggestion
        }
        
    except Exception as e:
        console_logger.error(f"Suggestion generation failed: {str(e)}")
        return {
            "next_suggestion": "Erzähl mir mehr über deine Prank-Idee! Was soll das Szenario sein und wer ist der Anrufer?"
        }
