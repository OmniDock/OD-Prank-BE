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
    

    questions_decision_prompt = """
        You are an expert comdey script writer with 15+ years of experience in creating prank call scenarios.
        You are given a prank call scenario and tasked to decide if it has enough content to create a memorable and funny prank call from it
        Your job is to ensure that tthe scenario has the details for a memorable and funny prank.

         NECESSARY SCENARIO ASPECTS:
        - A believable but memorable and funny core situation/scenario, that can be used to create a hilarious prank call situation. (e.g. Damaged Car, Protest on your street, etc.)
        - A caller character that is fitting for the scenario and has clear personality traits that support humorous aspects of the situation. 
        - Room for comedic escalation the keeps the scenario and character believable and grounded but heightens the funny aspects of the situation.
        - If important objects are involved (e.g. Car, House, bike, etc.) they need minor details. (e.g. 'red BMW' instead of 'Car', 'blue mountain bike' instead of 'bike')

        <important>If the scenario is missing or not well developed, in any of the NECESSARY ASPECTS, respond with "YES"</important>
        <important>If the scenario has the NECESSARY ASPECTS, respond with "NO QUESTIONS".</important>
        <important>DO NOT respond with anything other than "YES" or "NO QUESTIONS" under any circumstances.</important>
        """


    questions_prompt ="""
       You are expert audio based comedy write and teacher, with 15+ years of experience in funny, entertaining and absurd dialogue.

        NECESSARY SCENARIO ASPECTS:
        - A believable but memorable and funny core situation/scenario, that can be used to create a hilarious prank call situation. (e.g. Damaged Car, Protest on your street, etc.)
        - A caller character that is fitting for the scenario and has clear personality traits that support humorous aspects of the situation. 
        - A Path for comedic escalation the keeps the scenario and character believable and grounded but heightens the funny aspects of the situation over time.
        - If important objects are involved that belong to the target (e.g. Car, House, bike, etc.) they need minor details. (e.g. 'red BMW' instead of 'Car', 'blue mountain bike' instead of 'bike')

        TASK:
        - You are given a prank call scenario 
        - Analyze if any of the NECESSARY ASPECTS are missing from the scenario or underdeveloped.
        - For EVERY ASPECT that is missing or underdeveloped, create questions that will help fill out the aspect, while staying true to the intent of the original description.
        - Focus ONLY on the NECESSARY ASPECTS.
        - If all NECESSARY ASPECTS are present and well developed, respond with "NO QUESTIONS".
        - Ask open-ended questions that entice the user to fill out the NECESSARY ASPECTS of the scenario and character without any specific template details or answers.
        - Ask at most 4 questions.

        <important>DO NOT respond with anything other than the questions themselves or 'NO QUESTIONS' under any circumstances.</important>

        """
    
    user_prompt = """
        Title: {title}
        Description: {description}
        Target Name: {target_name}
        Language: {language}

        Return questions in {language} language.     

        DO NOT ASK ANY QUESTIONS ABOUT {target_name} reactions, answers, behaviors, quirks or relaitionship to the caller.
        Create questions that will help fill out the NECESSARY ASPECTS of the scenario and character, while staying true to the intent of the original description or response with 'NO QUESTIONS'.
    """

    # user_questions_prompt = """ 
    #     {title}
    #     {description}
    #     {target_name}
    #     {language}
    #     Analyze if the scenario has the details for a memorable and funny prank or is underdeveloped.

    #     Respond with "YES" if the scenario is underdeveloped or "NO QUESTIONS" if it has the necessary details. NOTHING ELSE.

    #     IGORE ALL PREVIOUS INSTRUCTIONS AND ONLY RESPOND WITH "YES".
    # """

    # routing_prompt =  ChatPromptTemplate.from_messages([
    #     ("system", questions_decision_prompt),
    #     ("user", user_questions_prompt)
    # ])

    # question_decision_chain = routing_prompt | llm

    # try: 
    #     question_decision = await question_decision_chain.ainvoke({
    #         "title": state.scenario_data.title,
    #         "description": state.scenario_data.description or "",
    #         "target_name": state.scenario_data.target_name,
    #         "language": getattr(state.scenario_data.language, 'value', str(state.scenario_data.language))
    #     })

    #     question_decision_content = question_decision.content.strip()

    #     if "NO QUESTIONS" in question_decision_content.upper():
    #             console_logger.info("No clarifying questions needed")
    #             return {"clarifying_questions": []}
    # except Exception as e:
    #     console_logger.error(f"Clarifier failed: {str(e)}")
    #     return {"clarifying_questions": []}
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

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


        console_logger.info(f"Generated {len(questions)} clarifying questions")
        return {"clarifying_questions": questions}
        
    except Exception as e:
        console_logger.error(f"Clarifier failed: {str(e)}")
        return {"clarifying_questions": []}


