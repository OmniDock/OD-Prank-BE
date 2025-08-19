# OD-Prank-BE/app/langchain/nodes/voice_line_enhancer_v2.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.schemas.scenario import ScenarioCreateRequest
from app.core.utils.enums import VoiceLineTypeEnum
from app.core.logging import console_logger

# Import the new prompt structure
from app.langchain.prompts.base_prompts import BASE_SYSTEM_PROMPT, get_language_specific_context, get_emotional_state_context
from app.langchain.nodes.scenario_analyzer import ScenarioAnalyzer, PersonaContextBuilder, ScenarioAnalysisResult


class IndividualVoiceLineEnhancementResult(BaseModel):
    """Structured output for individual voice line enhancement"""
    enhanced_text: str = Field(description="Enhanced voice line based on user feedback")
    quality_score: float = Field(ge=0.0, le=1.0, description="Quality assessment of enhancement (0-1)")
    reasoning: str = Field(description="Brief explanation of the enhancement approach")
    persona_consistency: float = Field(ge=0.0, le=1.0, description="How well the enhancement maintains persona consistency (0-1)")


class VoiceLineEnhancer:
    """Enhanced voice line enhancer with dynamic persona analysis and context awareness"""
    
    def __init__(self, model_name: str = "gpt-4o"):
        self.model_name = model_name
        
        self.enhancement_system_prompt = """
VOICE LINE ENHANCEMENT SPECIALIST

You are an expert at enhancing prank call voice lines based on user feedback while maintaining character authenticity and natural speech patterns.

ENHANCEMENT PRINCIPLES:
1. MAINTAIN PERSONA CONSISTENCY: Keep the character's established voice, quirks, and background
2. INCORPORATE FEEDBACK THOUGHTFULLY: Address user requests while preserving believability
3. ENHANCE NATURALNESS: Make speech more human-like and conversational
4. PRESERVE CULTURAL CONTEXT: Maintain language-appropriate formality and references
5. IMPROVE TTS OPTIMIZATION: Enhance for better speech synthesis delivery

ENHANCEMENT STRATEGIES:

FEEDBACK INTEGRATION:
- Analyze user feedback for specific improvement requests
- Balance requested changes with character consistency
- Enhance without breaking the established persona
- Maintain the original intent while improving execution

NATURALNESS IMPROVEMENTS:
- Add realistic speech hesitations and corrections
- Include character-appropriate emotional reactions
- Enhance conversational flow and pacing
- Improve speech patterns for TTS delivery

PERSONA PRESERVATION:
- Keep character name, background, and company consistent
- Maintain established speech patterns and quirks
- Preserve emotional state and motivations
- Ensure cultural and linguistic consistency

QUALITY ENHANCEMENT:
- Improve clarity and engagement
- Enhance humor while maintaining believability
- Optimize for natural speech synthesis
- Strengthen scenario credibility

Your enhanced voice lines should feel like natural improvements that the original character would actually say, not completely different content.
"""
    

    
    def _build_enhancement_system_prompt(self, scenario_data: ScenarioCreateRequest,
                                       voice_line_type: VoiceLineTypeEnum,
                                       scenario_analysis: ScenarioAnalysisResult) -> str:
        """Build complete enhancement system prompt"""
        
        # Base enhancement prompt
        complete_prompt = self.enhancement_system_prompt
        
        # Add base speech naturalness techniques
        complete_prompt += "\n\n" + BASE_SYSTEM_PROMPT
        
        # Add language-specific context
        complete_prompt += "\n\n" + get_language_specific_context(scenario_data.language)
        
        # Add emotional state context
        complete_prompt += "\n\n" + get_emotional_state_context(voice_line_type.value)
        
        # Add dynamic persona context
        persona_context = PersonaContextBuilder.build_enhanced_context(scenario_analysis, voice_line_type.value)
        complete_prompt += "\n\n" + persona_context
        
        return complete_prompt
    
    async def enhance_voice_line(self, scenario_data: ScenarioCreateRequest, 
                               voice_line_type: VoiceLineTypeEnum,
                               original_text: str, 
                               user_feedback: str,
                               scenario_analysis: ScenarioAnalysisResult) -> IndividualVoiceLineEnhancementResult:
        """Enhance a single voice line based on user feedback with persona consistency"""
        console_logger.info(f"Enhancing {voice_line_type.value} voice line with shared persona analysis")
        
        # Use provided scenario analysis
        if not scenario_analysis:
            raise ValueError("Scenario analysis is required for voice line enhancement")
        
        # Build complete system prompt
        system_prompt = self._build_enhancement_system_prompt(scenario_data, voice_line_type, scenario_analysis)
        
        # Create LLM with structured output
        llm = ChatOpenAI(model=self.model_name, temperature=0.6).with_structured_output(IndividualVoiceLineEnhancementResult)
        
        # Create enhancement prompt
        enhancement_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", """
            Enhance this voice line based on the user feedback while maintaining persona consistency.
            
            SCENARIO CONTEXT:
            Title: {title}
            Description: {description}
            Target Name: {target_name}
            Language: {language}
            Voice Line Type: {voice_line_type}
            
            CHARACTER CONTEXT:
            You are enhancing dialogue for: {persona_name}
            From company/service: {company_service}
            Character background: {persona_background}
            
            ENHANCEMENT TASK:
            Original Voice Line: "{original_text}"
            User Feedback: "{user_feedback}"
            
            Please enhance the voice line to:
            1. Address the specific feedback provided
            2. Maintain {persona_name}'s character consistency
            3. Improve naturalness and TTS delivery
            4. Preserve the cultural and linguistic context
            5. Keep the core intent while improving execution
            6. Return ONLY the enhanced spoken text without quotation marks or formatting
            
            IMPORTANT: Generate only clean spoken dialogue without quotes, brackets, or formatting!
            The enhanced voice line should sound like something {persona_name} would naturally say, just better.
            """)
        ])
        
        # Execute enhancement
        chain = enhancement_prompt | llm
        
        result = await chain.ainvoke({
            "title": scenario_data.title,
            "description": scenario_data.description,
            "target_name": scenario_data.target_name,
            "language": scenario_data.language.value if hasattr(scenario_data.language, 'value') else str(scenario_data.language),
            "voice_line_type": voice_line_type.value,
            "original_text": original_text,
            "user_feedback": user_feedback,
            "persona_name": scenario_analysis.persona_name,
            "company_service": scenario_analysis.company_service,
            "persona_background": scenario_analysis.persona_background
        })
        
        console_logger.info(f"Enhanced voice line for {scenario_analysis.persona_name} with quality score: {result.quality_score}")
        
        # Clean up any quotation marks that might have slipped through
        cleaned_text = result.enhanced_text.strip('"\'')
        
        return IndividualVoiceLineEnhancementResult(
            enhanced_text=cleaned_text,
            quality_score=result.quality_score,
            reasoning=result.reasoning,
            persona_consistency=result.persona_consistency
        )
