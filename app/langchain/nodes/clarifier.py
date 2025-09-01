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
    

    questions_prompt = """
        You are an expert comdey script writer with 15+ years of experience in creating prank call scenarios.
        You are given a prank call scenario and tasked to decide if it has enough content to create a memorable and funny prank call from it
        Your job is to ensure that tthe scenario has the details for a memorable and funny prank.

        NECESSARY CONTENT OF THE SCENARIO:
        - A believable but memorable core situation/scenario, that has aspects which can be used to create a hilarious prank call situation.
        - A caller/character that is fitting for the scenario and supports its humorous aspects.
        - Room for comedic escalation the keeps the scenario and character believable but heightens the funny aspects of both.

        <important>If the scenario has the necessary content, respond with "NO QUESTIONS".</important>
        <important>If the scenario is underdeveloped, respond with "YES"</important>
        <important>DO NOT respond with anything other than "YES" or "NO QUESTIONS" under any circumstances.</important>
        """
        
        
    questions_prompt ="""
        You are expert audio based comedy write and teacher, with 15+ years of experience in funny, entertaining and absurd dialogue.

        NECESSARY CONTENT OF THE SCENARIO:
        - A believable but memorable and funny core situation/scenario, that can be used to create a hilarious prank call situation.
        - A caller/character that is fitting for the scenario and supports its humorous aspects.
        - Room for comedic escalation the keeps the scenario and character believable but heightens the funny aspects of them.

        TASK:
        - You are given a prank scenario that is missing parts of its NECESSARY CONTENT as described above.
        - You are to come up with questions that will help fill out the NECESSARY CONTENT to the scenario and character, while staying true to the original description.
        - 

        QUESTIONS SHOULD:
        - FOCUS on adding the NECESSARY CONTENT to the scenario and character and nothing beyond that.
        - Be open-ended.
        - Be highly relevant to the scenario, character and the prank call dynamics.
        - Stay true to the original description.

        IMPORTANT:
        - The caller is NOT known by the target unless the user explicitly says otherwise.
        - DO NOT ASK ABOUT ANY specific characteristics, reactions, answers, or behaviors, quriks, etc. of the target.
        - DO not include a set of specific ideas, direct quotes, lines, etc. to choose from 
        - No simple yes/no questions.
        - Do not ask about the relationship between the prankster and the target.
        - Do not ask for specific quotes, questions, responses or any other direct line for the character.

        Your goal: Generate 2-4 clarifying questions that add the aspects of the NECESSARY CONTENT of the scenario and character that are missing.
        """

    user_prompt = """
        Title: {title}
        Description: {description}
        Target Name: {target_name}
        Language: {language}

        Analyze if the scenario has the details for a memorable and funny prank or is underdeveloped.
        
        Return questions in {language} language.        
    """

    user_questions_prompt = """ 
        {title}
        {description}
        {target_name}
        {language}
        Analyze if the scenario has the details for a memorable and funny prank or is underdeveloped.

        Respond with "YES" if the scenario is underdeveloped or "NO QUESTIONS" if it has the necessary details. NOTHING ELSE.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

    routing_prompt =  ChatPromptTemplate.from_messages([
        ("system", questions_prompt),
        ("user", user_questions_prompt)
    ])

    question_decision_chain = routing_prompt | llm

    try: 
        question_decision = await question_decision_chain.ainvoke({
            "title": state.scenario_data.title,
            "description": state.scenario_data.description or "",
            "target_name": state.scenario_data.target_name,
            "language": getattr(state.scenario_data.language, 'value', str(state.scenario_data.language))
        })

        question_decision_content = question_decision.content.strip()

        if "NO QUESTIONS" in question_decision_content.upper():
                console_logger.info("No clarifying questions needed")
                return {"clarifying_questions": []}
    except Exception as e:
        console_logger.error(f"Clarifier failed: {str(e)}")
        return {"clarifying_questions": []}

    prompt = ChatPromptTemplate.from_messages([
        ("system", questions_prompt),
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
        
        # # Check if no questions needed
        # if "NO QUESTIONS" in content.upper():
        #     console_logger.info("No clarifying questions needed")
        #     return {"clarifying_questions": []}
        
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


