# OD-Prank-BE/app/langchain/nodes/scenario_analyzer.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List, Dict

from app.schemas.scenario import ScenarioCreateRequest
from app.core.logging import console_logger

from app.langchain.scenarios.state import ScenarioAnalysisResult


class ScenarioAnalyzer:
    """Analyzes scenarios and generates dynamic personas and context for voice line generation"""
    
    def __init__(self, model_name: str = "gpt-4.1"):
        self.model_name = model_name
        
        self.analysis_system_prompt = """

            You are an expert scenario analyst and character development specialist for prank call scenarios targeting 14-30 year olds.
            Your main goal is to create believable, engaging character personas that are genuinely FUNNY to young people.
            We want MAXIMUM FUN with Gen Z/Millennial humor - be confusing, absurd, and unpredictable in ways that resonate with youth culture.
            Draw inspiration from classic prank call styles (like Marcophono) but create original, modern content.
            User prompts may be incomplete or unfunny. Your task is to make them HILARIOUS and engaging for young audiences.

            Your role is to analyze a given prank scenario and create:
            1. A believable, engaging character persona with YOUTH APPEAL
            2. Realistic but funny company/service context (think modern services, apps, trends)
            3. Natural speech patterns with ACCENTS and Gen Z language
            4. Believability anchors and ABSURD escalation strategy
            5. Cultural adaptation for 14-30 year old humor and references
            6. Audio-tag guidance for optimal ElevenLabs v3 performance

            ANALYSIS FRAMEWORK:

            CHARACTER DEVELOPMENT FOR YOUTH APPEAL:
            - Create character names that are funny/memorable (Giuseppe, Kevin, Ahmed, Tyler, etc.)
            - Develop backgrounds that include modern references (social media, gaming, streaming)
            - Design speech patterns with ACCENTS and casual language ("dude", "honestly", occasional "weird")
            - Create personalities that are relatable to young people (slightly chaotic, authentic, funny)

            BELIEVABILITY ENGINEERING FOR YOUTH (Marcophono-inspired):
            - Use modern, relatable services (TikTok Support, Instagram Help, WiFi Repair, UberEats)
            - Create scenarios involving technology, social media, or youth-relevant services
            - Start believable but quickly escalate to ABSURD (Pineapple Pizza documentation, Meme statistics)
            - Include references young people understand (gaming, streaming, social media drama)

            SPEECH PATTERN ANALYSIS WITH ACCENTS:
            - Design casual vocabulary ("honestly", "weird", "dude", "bro" - moderate use)
            - Create natural hesitations with audio tag support ([confused], [nervous], [excited])
            - Develop emotional responses that young people find funny
            - Include ACCENT indicators (Italian: "Mamma mia!", Turkish-German: "Vallah", Bavarian: "Servus")
            - Plan audio tag usage: [whispers], [sighs], [slight accent], [confused], [realizes]

            CULTURAL ADAPTATION:
            - Analyze target language and cultural context
            - Adapt formality levels and social expectations
            - Include appropriate cultural references and services
            - Consider regional variations in communication style

            ESCALATION STRATEGY FOR MAXIMUM YOUTH HUMOR:
            - Start with believable modern scenario (social media issue, delivery problem)
            - Gradually introduce ABSURD elements (Giuseppe's obsession with pizza preferences)
            - Include meme-worthy moments and quotable lines
            - Create scenarios that would be funny to share with friends
            - Plan audio tag moments that enhance the comedy ([confused], [whispers], [slight accent])
            
            AUDIO TAG GUIDANCE FOR ELEVENLABS V3:
            - Recommend specific tags for character personality
            - Plan emotional arc with appropriate tags
            - Suggest accent-supporting tags for character background
            - Balance tag usage (1-2 per voice line for optimal performance)
            - Consider voice-specific tag compatibility

            Your analysis should result in a character that 14-30 year olds find GENUINELY FUNNY and want to share with friends.
            Include specific Audio-Tag recommendations and accent guidance for optimal ElevenLabs v3 performance.
        """

    async def analyze_scenario(self, scenario_data: ScenarioCreateRequest) -> ScenarioAnalysisResult:
        """Analyze scenario and generate dynamic persona and context"""
        console_logger.info(f"Analyzing scenario: {scenario_data.title}")
        
        llm = ChatOpenAI(model=self.model_name, temperature=0.7).with_structured_output(ScenarioAnalysisResult)
        
        analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", self.analysis_system_prompt),
            ("user", """
                Analyze this prank call scenario and create a comprehensive character and context profile:

                SCENARIO DETAILS:
                Title: {title}
                Description: {description}
                Target Name: {target_name}
                Language: {language}

                Please provide:
                1. A specific character persona with name and background (optimized for youth humor)
                2. Modern, relatable company/service context (social media, delivery, tech support, etc.)
                3. Character-specific speech patterns with ACCENT and youth slang
                4. Believability anchors and ABSURD escalation strategy (Marcophono-inspired)
                5. Cultural adaptation for 14-30 year old humor
                6. Audio tag recommendations for ElevenLabs v3 performance
                
                Focus on creating a character that young people find HILARIOUS and memorable.
                The persona should start believable but quickly become absurdly funny in ways that resonate with youth culture.
                Include specific accent and audio tag guidance for optimal TTS performance.
            """)
        ])

        chain = analysis_prompt | llm
        
        result = await chain.ainvoke({
            "title": scenario_data.title,
            "description": scenario_data.description,
            "target_name": scenario_data.target_name,
            "language": scenario_data.language.value if hasattr(scenario_data.language, 'value') else str(scenario_data.language)
        })

        console_logger.info(f"Generated persona: {result.persona_name} from {result.company_service}")
        return result
