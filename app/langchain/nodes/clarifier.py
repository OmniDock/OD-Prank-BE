"""
Clarifier node - detects missing information and generates questions
"""
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.langchain.state import ScenarioState
from app.core.logging import console_logger


async def clarifier_node(state: ScenarioState) -> dict:
    """
    Check if critical information is missing and generate clarifying questions
    """
    console_logger.info("Running clarifier node")
    
    # Skip if clarification not required or already provided
    if not state.require_clarification or state.clarifications:
        console_logger.info("Skipping clarification - not required or already provided")
        return {"clarifying_questions": []}
    
    system_prompt = """
        You are an expert in creating deadpan-serious prank call scenarios.
        
        Your job is to ensure the scenario has the ESSENTIAL details for a memorable prank.
        
        Only ask questions if CRITICAL information is missing. Ask 1-3 questions MAXIMUM.
        Focus on what's absolutely necessary:
        1. The CORE situation/problem (what's the main premise)
        2. ONE key absurd element that makes it funny
        3. The caller's basic personality (if not clear from context)
        
        DO NOT ask about:
        - How the situation escalates (let creativity handle that)
        - Multiple twists or complications
        - Specific dialogue or phrases
        - When the actual call should happen
        - Real contact information
        - Payment or personal data
        
        Examples of descriptions that DON'T need questions:
        - "Pizza delivery insisting the customer ordered 50 pizzas with anchovies"
        - "Bank calling about suspicious purchase of 1000 rubber ducks"
        - "Package delivery for a life-size cardboard cutout of Nicolas Cage"
        - "Dentist office confirming appointment for wisdom teeth removal for their pet hamster"
        
        Examples that MIGHT need 1-2 questions:
        - "A funny prank call" → What's the situation? Who's calling?
        - "Pizza delivery prank" → What's special about this delivery? What has gone wrong? 
        
        <important>Default to NO questions unless something is truly unclear.</important>
        <important>If you can understand the basic premise, don't ask for more details.</important>
        <important>Never ask more than 3 questions, even if more details could help.</important>
        <important>Do NOT ask how things escalate or develop - that's for the scenario generation.</important>
    """

    user_prompt = """
        Title: {title}
        Description: {description}
        Target Name: {target_name}
        Language: {language}

        Check if the CORE premise is clear. If yes, respond with "NO QUESTIONS".
        
        Only ask 1-3 questions if you truly cannot understand what the prank is about.
        Focus only on the missing ESSENTIAL information.
        
        Return questions in {language} language.
        
        Remember: If you understand the basic idea, that's enough. Don't ask for elaboration.
    """

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    chain = prompt | llm
    
    try:
        result = await chain.ainvoke({
            "title": state.scenario_data.title,
            "description": state.scenario_data.description or "",
            "target_name": state.scenario_data.target_name,
            "language": getattr(state.scenario_data.language, 'value', str(state.scenario_data.language))
        })
        
        content = result.content.strip()
        
        # Check if no questions needed
        if "NO QUESTIONS" in content.upper():
            console_logger.info("No clarifying questions needed")
            return {"clarifying_questions": []}
        
        # Parse questions
        questions = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                # Remove numbering and bullet points
                line = line.lstrip('1234567890.-• ')
                if line:
                    questions.append(line)
        
        # Limit to 3 questions (changed from 5)
        questions = questions[:3]
        
        console_logger.info(f"Generated {len(questions)} clarifying questions")
        return {"clarifying_questions": questions}
        
    except Exception as e:
        console_logger.error(f"Clarifier failed: {str(e)}")
        return {"clarifying_questions": []}
