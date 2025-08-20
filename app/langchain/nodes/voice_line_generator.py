# OD-Prank-BE/app/langchain/nodes/voice_line_generator_v2.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List

from app.schemas.scenario import ScenarioCreateRequest
from app.core.utils.enums import VoiceLineTypeEnum, LanguageEnum
from app.core.logging import console_logger

# Import the new prompt structure
from app.langchain.prompts.base_prompts import BASE_SYSTEM_PROMPT, get_language_specific_context, get_emotional_state_context
from app.langchain.prompts.voice_line_prompts import (
    OPENING_VOICE_LINES_PROMPT,
    RESPONSE_VOICE_LINES_PROMPT, 
    QUESTION_VOICE_LINES_PROMPT,
    CLOSING_VOICE_LINES_PROMPT
)
from app.langchain.nodes.scenario_analyzer import  PersonaContextBuilder, ScenarioAnalysisResult


class VoiceLineGenerationResult(BaseModel):
    """Structured output for voice line generation"""
    voice_lines: List[str] = Field(description="Generated voice lines for the specified type")
    quality_score: float = Field(ge=0.0, le=1.0, description="Quality assessment of generated lines (0-1)")
    reasoning: str = Field(description="Brief explanation of the generation approach")


class VoiceLineGenerator:
    """Enhanced voice line generator with dynamic persona analysis and separated prompts"""
    
    def __init__(self, model_name: str = "gpt-4o"):
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
            language: LanguageEnum = LanguageEnum.GERMAN
        ) -> VoiceLineGenerationResult:
        """Generate voice lines with shared scenario analysis"""
        console_logger.info(f"Generating {count} {voice_line_type.value} voice lines using shared persona analysis")
        console_logger.info(f"Voice line type: {voice_line_type.value}, Persona: {scenario_analysis.persona_name if scenario_analysis else 'None'}")
        
        # Use provided scenario analysis
        if not scenario_analysis:
            raise ValueError("Scenario analysis is required for voice line generation")
        
        # Build complete system prompt
        system_prompt = self._build_complete_system_prompt(scenario_data, voice_line_type, scenario_analysis)
        
        # Create LLM with structured output - higher temperature for more natural speech variation
        llm = ChatOpenAI(model=self.model_name, temperature=0.7).with_structured_output(VoiceLineGenerationResult)
        
        # Create prompt template
        generation_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", """
            Generate {count} {voice_line_type} voice lines for this prank scenario.
            
            CRITICAL: These are {voice_line_type} voice lines - NOT opening lines!
            - OPENING: First contact, introduce yourself and purpose (USE target name)
            - QUESTION: Ask follow-up questions during ongoing conversation (AVOID overusing name)
            - RESPONSE: React to target's questions/objections in mid-conversation (AVOID overusing name)
            - CLOSING: End the call, wrap up the conversation (USE target name for farewell)
            
            NAME USAGE RULES:
            - OPENING & CLOSING: Include target name naturally
            - QUESTION & RESPONSE: Avoid using target name unless absolutely necessary
            - Don't repeat the name excessively - it sounds robotic and unnatural!
            
            IMPORTANT: Generate ONLY the spoken text without quotation marks or any formatting!
            
            CRITICAL: Make the dialogue sound NATURALLY HUMAN with realistic speech patterns:
            - Include natural hesitations: "Uhh...", "Well...", "Let's see..."
            - Use self-corrections: "I mean... actually, let me put it this way..."
            - Add thinking out loud: "Now where did I put... ah yes, here it is"
            - Include SSML breaks for natural pauses: <break time="0.3s" />
            - Use incomplete thoughts: "So the thing is... well, you know what I mean"
            - Add natural restarts: "What I'm trying to— sorry, let me start over"
            
            Use the persona analysis and context provided to create natural, engaging dialogue that:
            1. Maintains character consistency
            2. Sounds completely natural when spoken with human imperfections
            3. Fits the cultural and linguistic context
            4. Follows the escalation strategy outlined
            5. Incorporates the character's speech patterns and quirks
            6. MATCHES THE SPECIFIC {voice_line_type} CONTEXT - not a fresh introduction!
            7. NO quotation marks, brackets - just pure spoken dialogue!
            8. MUST include realistic speech patterns and natural hesitations!
            
            SCENARIO DETAILS:
            Title: {title}
            Description: {description}
            Target Name: {target_name}
            Language: {language}
            
            Remember: You are {persona_name} from {company_service}. Stay in character!
            Generate {voice_line_type} lines that fit naturally in the middle of an ongoing conversation!
            Return only clean spoken text without any quotation marks or formatting!
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
        
        # Clean up any quotation marks that might have slipped through (but preserve SSML tags)
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
