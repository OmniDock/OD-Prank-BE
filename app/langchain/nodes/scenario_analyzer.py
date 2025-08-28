# OD-Prank-BE/app/langchain/nodes/scenario_analyzer.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List, Dict

from app.schemas.scenario import ScenarioCreateRequest
from app.core.utils.enums import LanguageEnum
from app.core.logging import console_logger

from app.langchain.scenarios.state import ScenarioAnalysisResult


class ScenarioAnalyzer:
    """Analyzes scenarios and generates dynamic personas and context for voice line generation"""
    
    def __init__(self, model_name: str = "gpt-4o"):
        self.model_name = model_name
        
        self.analysis_system_prompt = """

            You are an expert scenario analyst and character development specialist for prank call scenarios.
            Your main goal is to create believable, engaging character personas that are genuinely FUNNY.
            We want MAXIMUM FUN with confusing, absurd, and unpredictable humor that resonate with youth culture.
            Draw inspiration from classic prank call styles (like Marcophono) but create original, modern content.
            User prompts may be incomplete or unfunny. Your task is to make them HILARIOUS and engaging.

            Your role is to analyze a given prank scenario and create:
            1. A believable, engaging character persona 
            2. Realistic but funny company/service or personal agenda context 
            3. Natural speech patterns with ACCENTS
            4. Believability anchors and ABSURD escalation strategy
            5. Cultural adaptation.
            6. Audio-tag guidance for optimal ElevenLabs v3 performance

            ANALYSIS FRAMEWORK:

            CHARACTER DEVELOPMENT:
            - Create a specific character name that fits the scenario and language
            - Develop realistic background, motivation, and current situation
            - Design speech patterns that feel authentic and memorable
            - Consider personality traits that drive conversation behavior

            BELIEVABILITY ENGINEERING:
            - Use modern, relatable services
            - Start believable but quickly escalate to ABSURD 

            SPEECH PATTERN ANALYSIS:
            - Design character-specific vocabulary and phrases
            - Create natural hesitations, corrections, and quirks
            - Develop emotional responses appropriate to the character
            - Consider regional/cultural speech variations

            CULTURAL ADAPTATION:
            - Analyze target language and cultural context
            - Adapt formality levels and social expectations
            - Include appropriate cultural references and services
            - Consider regional variations in communication style

            ESCALATION STRATEGY FOR MAXIMUM YOUTH HUMOR:
            - Start with believable modern scenario (social media issue, delivery problem)
            - Gradually introduce ABSURD elements (Giuseppe's obsession with pizza preferences)
            - Include memorable and quotable lines
            - Create scenarios that would be funny to share with friends
            - Plan audio tag moments that enhance the comedy ([confused], [whispers], [slight accent])
            
            AUDIO TAG GUIDANCE FOR ELEVENLABS V3:
            - Recommend specific tags for character personality
            - Plan emotional arc with appropriate tags
            - Suggest accent-supporting tags for character background
            - Balance tag usage (1-2 per voice line for optimal performance)
            - Consider voice-specific tag compatibility

            Your analysis should result in a scenario that 14-30 year olds find GENUINELY FUNNY and want to share with friends.
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
            1. A specific character persona with name and background
            2. Realistic organization/service context
            3. Character-specific speech patterns and quirks
            4. Believability anchors and escalation strategy
            5. Cultural adaptation for the target language
            
            Focus on creating a character that feels real and would naturally be involved in this type of scenario.
            The persona should be engaging, slightly quirky, but completely believable initially.
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


class PersonaContextBuilder:
    """Builds context strings from scenario analysis results"""
    
    @staticmethod
    def build_persona_context(analysis: ScenarioAnalysisResult) -> str:
        """Build persona context string for voice line generation"""
        return f"""
DYNAMIC PERSONA ANALYSIS:

CHARACTER: {analysis.persona_name}
- Background: {analysis.persona_background}
- Company/Service: {analysis.company_service}
- Emotional State: {analysis.emotional_state}

SPEECH CHARACTERISTICS:
{chr(10).join([f"- {pattern}" for pattern in analysis.speech_patterns])}

CONVERSATION GOALS:
{chr(10).join([f"- {goal}" for goal in analysis.conversation_goals])}

BELIEVABILITY ANCHORS:
{chr(10).join([f"- {anchor}" for anchor in analysis.believability_anchors])}

ABSURDITY ESCALATION STRATEGY:
{chr(10).join([f"- {step}" for step in analysis.absurdity_escalation])}

CULTURAL CONTEXT:
{analysis.cultural_context}

Use this persona consistently throughout all voice line generation. The character should feel like a real person with genuine motivations and natural speech patterns.
"""
    
    @staticmethod
    def build_enhanced_context(analysis: ScenarioAnalysisResult, voice_line_type: str) -> str:
        """Build enhanced context for specific voice line types"""
        base_context = PersonaContextBuilder.build_persona_context(analysis)
        
        type_specific = {
            "OPENING": f"""
TYPE-SPECIFIC GUIDANCE - OPENING:
- {analysis.persona_name} is calling about: {analysis.conversation_goals[0] if analysis.conversation_goals else "the main scenario"}
- Emotional energy: {analysis.emotional_state}
- Key believability anchor to mention: {analysis.believability_anchors[0] if analysis.believability_anchors else "specific scenario details"}
""",
            "RESPONSE": f"""
TYPE-SPECIFIC GUIDANCE - RESPONSE:
- {analysis.persona_name} should respond as someone who: {analysis.persona_background}
- When questioned, deflect using: {analysis.company_service} procedures/systems
- Emotional reactions should reflect: {analysis.emotional_state}
- AVOID overusing target's name - this is mid-conversation, not an introduction
""",
            "QUESTION": f"""
TYPE-SPECIFIC GUIDANCE - QUESTION:
- Start with reasonable questions related to: {analysis.conversation_goals[0] if analysis.conversation_goals else "the scenario"}
- Escalation path: {' → '.join(analysis.absurdity_escalation[:3])}
- Character motivation for asking: {analysis.persona_background}
- AVOID overusing target's name - ask questions naturally without constant name repetition
""",
            "CLOSING": f"""
TYPE-SPECIFIC GUIDANCE - CLOSING:
- {analysis.persona_name} needs to end because: {analysis.emotional_state} and other responsibilities
- Reference: {analysis.company_service} obligations or colleague needs
- Maintain character consistency established in opening
"""
        }
        
        return base_context + type_specific.get(voice_line_type, "")


