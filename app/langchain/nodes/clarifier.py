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
        
        Your job is to check if the scenario description has enough detail to create a believable prank.
        
        Ask maximum 3 clarifying questions ONLY if critical scenario details are missing:
        - What specific problem/situation is the caller presenting? (e.g., wrong pizza order, package issue)
        - What absurd twist or escalation should happen? (e.g., asking them to sing, confirm door color)
        - What persona details would make it more believable? (e.g., company name, accent, attitude)
        
        DO NOT ask about:
        - When the actual call should happen
        - Real contact information
        - Payment or personal data
        - Anything unrelated to the prank content itself
        
        If the description already contains enough detail to work with, respond with: NO QUESTIONS
    """

    user_prompt = """
        Title: {title}
        Description: {description}
        Target Name: {target_name}
        Language: {language}

        Check if we have enough detail to create a believable prank scenario.
        If key details about the prank situation, absurd elements, or character are missing, ask up to 3 questions.
        Return questions in {language} language.
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
        
        # Limit to 3 questions
        questions = questions[:3]
        
        console_logger.info(f"Generated {len(questions)} clarifying questions")
        return {"clarifying_questions": questions}
        
    except Exception as e:
        console_logger.error(f"Clarifier failed: {str(e)}")
        return {"clarifying_questions": []}
