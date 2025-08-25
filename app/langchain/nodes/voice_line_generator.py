# OD-Prank-BE/app/langchain/nodes/voice_line_generator_v2.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List

from app.schemas.scenario import ScenarioCreateRequest
from app.core.utils.enums import VoiceLineTypeEnum
from app.core.logging import console_logger

# Import the new prompt structure
from app.langchain.prompts.base_prompts import BASE_SYSTEM_PROMPT, get_language_specific_context, get_emotional_state_context
from app.langchain.prompts.voice_line_prompts import (
    OPENING_VOICE_LINES_PROMPT,
    RESPONSE_VOICE_LINES_PROMPT, 
    QUESTION_VOICE_LINES_PROMPT,
    CLOSING_VOICE_LINES_PROMPT
)
from app.langchain.scenarios.state import ScenarioAnalysisResult
from app.langchain.prompts.persona_context_builder import PersonaContextBuilder


class VoiceLineGenerationResult(BaseModel):
    """Structured output for voice line generation"""
    voice_lines: List[str] = Field(description="Generated voice lines for the specified type")
    quality_score: float = Field(ge=0.0, le=1.0, description="Quality assessment of generated lines (0-1)")
    reasoning: str = Field(description="Brief explanation of the generation approach")


class VoiceLineGenerator:
    """Enhanced voice line generator with dynamic persona analysis and separated prompts"""
    
    def __init__(self, model_name: str = "gpt-4.1"):
        self.model_name = model_name
        
    def _get_voice_line_prompt(self, voice_line_type: VoiceLineTypeEnum) -> str:
        """Get the appropriate prompt for the voice line type"""
        prompt_map = {
            VoiceLineTypeEnum.OPENING: OPENING_VOICE_LINES_PROMPT,
            VoiceLineTypeEnum.RESPONSE: RESPONSE_VOICE_LINES_PROMPT,
            VoiceLineTypeEnum.QUESTION: QUESTION_VOICE_LINES_PROMPT,
            VoiceLineTypeEnum.CLOSING: CLOSING_VOICE_LINES_PROMPT
        }
        return prompt_map.get(voice_line_type, OPENING_VOICE_LINES_PROMPT)
    

    
    def _build_complete_system_prompt(self, scenario_data: ScenarioCreateRequest, 
                                    voice_line_type: VoiceLineTypeEnum,
                                    scenario_analysis: ScenarioAnalysisResult) -> str:
        """Build the complete system prompt with all components"""
        
        # Base system prompt
        complete_prompt = BASE_SYSTEM_PROMPT
        
        # Add language-specific context
        complete_prompt += "\n\n" + get_language_specific_context(scenario_data.language)
        
        # Add emotional state context
        complete_prompt += "\n\n" + get_emotional_state_context(voice_line_type.value)
        
        # Add dynamic persona context
        persona_context = PersonaContextBuilder.build_enhanced_context(scenario_analysis, voice_line_type.value)
        complete_prompt += "\n\n" + persona_context
        
        # Add voice line type specific prompt
        type_prompt = self._get_voice_line_prompt(voice_line_type)
        complete_prompt += "\n\n" + type_prompt
        
        return complete_prompt
    
    def _trim_to_count(self, voice_lines: List[str], keep_count: int) -> List[str]:
        """Trim voice lines to the requested count"""
        if len(voice_lines) > keep_count:
            return voice_lines[:keep_count]
        return voice_lines
    
    async def generate_voice_lines(
            self, 
            scenario_data: ScenarioCreateRequest, 
            voice_line_type: VoiceLineTypeEnum, 
            count: int,
            scenario_analysis: ScenarioAnalysisResult,
        ) -> VoiceLineGenerationResult:

        """Generate voice lines with shared scenario analysis"""    
        console_logger.info(f"Generating {count} {voice_line_type.value} voice lines using shared persona analysis")
        console_logger.info(f"Voice line type: {voice_line_type.value}, Persona: {scenario_analysis.persona_name if scenario_analysis else 'None'}")
        
        # Build complete system prompt
        system_prompt = self._build_complete_system_prompt(scenario_data, voice_line_type, scenario_analysis)
        
        # Create LLM with structured output - higher temperature for more natural speech variation
        llm = ChatOpenAI(model=self.model_name, temperature=0.7).with_structured_output(VoiceLineGenerationResult)
        
        # Create prompt template
        generation_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", """
                Generate {count} {voice_line_type} voice lines for this prank scenario.
                
                CRITICAL: These are {voice_line_type} voice lines - NOT opening lines! (Marcophono-style)
                - OPENING: First contact, introduce yourself and purpose (USE target name)
                - QUESTION: Ask follow-up questions during ongoing conversation (AVOID overusing name)
                - RESPONSE: React to target's questions/objections in mid-conversation (AVOID overusing name)
                - CLOSING: End the call, wrap up the conversation (USE target name for farewell)
                
                NAME USAGE RULES:
                - OPENING & CLOSING: Include target name naturally
                - QUESTION & RESPONSE: Avoid using target name unless absolutely necessary
                - Don't repeat the name excessively - it sounds robotic and unnatural!
                
                IMPORTANT: Generate ONLY the spoken text without quotation marks. Square-bracket audio tags (e.g., [sighs], [curious]) are allowed.
                
                YOUTH-OPTIMIZED: Make dialogue natural AND funny for 14-30 year olds (Marcophono-inspired):
                - Natural hesitations: "Uh...", "Like...", "Hmm...", "Wait what..."
                - Casual corrections: "I mean... uh, hold on..."
                - Thinking aloud: "Where did I put... oh here!", "Wait... that's weird"
                - Audio tags + punctuation: [confused] for confusion, ... for pauses, — for cuts
                - Incomplete thoughts: "The thing is... well, you know?"
                - Natural restarts: "What I was trying to say— forget it, dude"
                
                Use persona analysis for natural, engaging dialogue that:
                1. Maintains character consistency with moderate youth appeal
                2. Sounds natural with human imperfections AND is genuinely funny
                3. Appeals to younger audiences without overwhelming slang
                4. Follows escalation strategy (believable → absurd)
                5. Incorporates character speech patterns with ACCENTS
                6. Matches the specific {voice_line_type} CONTEXT
                7. Uses audio tags sparingly (1-2 per line) for realism
                8. Has natural speech patterns and hesitations!
                
                SCENARIO DETAILS:
                Title: {title}
                Description: {description}
                Target Name: {target_name}
                Language: {language}
                
                Remember: You are {persona_name} from {company_service} - stay in character but make it FUNNY!
                Generate {voice_line_type} lines that fit naturally in ongoing conversations!
                Return only spoken text (no quotation marks), audio tags in [square brackets] are allowed.
            """)
        ])
        
        # Execute generation
        chain = generation_prompt | llm
        
        result = await chain.ainvoke({
            "title": scenario_data.title,
            "description": scenario_data.description,
            "target_name": scenario_data.target_name,
            "language": scenario_data.language.value if hasattr(scenario_data.language, 'value') else str(scenario_data.language),
            "voice_line_type": voice_line_type.value,
            "count": count,
            "persona_name": scenario_analysis.persona_name,
            "company_service": scenario_analysis.company_service
        })
        
        # Clean up any quotation marks that might have slipped through (audio tags are preserved)
        cleaned_voice_lines = [line.strip('"\'') for line in result.voice_lines]
        
        # Trim to requested count
        sorted_result = self._trim_to_count(cleaned_voice_lines, count)
        
        console_logger.info(f"Generated {len(sorted_result)} voice lines for {scenario_analysis.persona_name}")
        
        return VoiceLineGenerationResult(
            voice_lines=sorted_result, 
            quality_score=result.quality_score, 
            reasoning=f"Generated as {scenario_analysis.persona_name}: {result.reasoning}"
        )
    
    # Convenience methods for each voice line type
    async def generate_opening_voice_lines(self, scenario_data: ScenarioCreateRequest, count: int, scenario_analysis: ScenarioAnalysisResult) -> VoiceLineGenerationResult:
        return await self.generate_voice_lines(scenario_data, VoiceLineTypeEnum.OPENING, count, scenario_analysis)
    
    async def generate_response_voice_lines(self, scenario_data: ScenarioCreateRequest, count: int, scenario_analysis: ScenarioAnalysisResult) -> VoiceLineGenerationResult:
        return await self.generate_voice_lines(scenario_data, VoiceLineTypeEnum.RESPONSE, count, scenario_analysis)
    
    async def generate_question_voice_lines(self, scenario_data: ScenarioCreateRequest, count: int, scenario_analysis: ScenarioAnalysisResult) -> VoiceLineGenerationResult:
        return await self.generate_voice_lines(scenario_data, VoiceLineTypeEnum.QUESTION, count, scenario_analysis)
    
    async def generate_closing_voice_lines(self, scenario_data: ScenarioCreateRequest, count: int, scenario_analysis: ScenarioAnalysisResult) -> VoiceLineGenerationResult:
        return await self.generate_voice_lines(scenario_data, VoiceLineTypeEnum.CLOSING, count, scenario_analysis)
