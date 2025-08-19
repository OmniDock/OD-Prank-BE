# OD-Prank-BE/app/langchain/nodes/voice_line_generator.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List

from app.schemas.scenario import ScenarioCreateRequest
from app.core.utils.enums import VoiceLineTypeEnum
from app.core.logging import console_logger


class VoiceLineGenerationResult(BaseModel):
    """Structured output for voice line generation"""
    voice_line: str = Field(description="Enhanced voice line for the specified type")
    quality_score: float = Field(ge=0.0, le=1.0, description="Quality assessment of generated lines (0-1)")
    reasoning: str = Field(description="Brief explanation of the generation approach")


class VoiceLineEnhancer:
    """Handles voice line enhancement with structured output"""
    
    def __init__(self, model_name: str = "gpt-4o"): 
        self.model_name = model_name

        self.base_system_prompt = """
          You are an expert prank call script writer specializing in creating engaging, humorous, and contextually appropriate voice lines optimized for ElevenLabs Text-to-Speech API.

                Your role is to enhance voice lines for prank call scenarios that are:
                - Entertaining and engaging
                - Contextually appropriate for the scenario
                - Natural and conversational
                - Varied in style and approach
                - Safe and respectful (no harmful content)
                - Optimized for ElevenLabs TTS models (Eleven v3, Multilingual v2, Flash v2.5, Turbo v2.5)

                ELEVENLABS TTS FORMATTING GUIDELINES:
                - Write text that sounds natural when spoken by AI
                - Use minimal punctuation for better flow
                - Leverage ElevenLabs audio tags in square brackets for enhanced expression:
                  * [laughter] - for laughing sounds
                  * [sigh] - for sighing
                  * [whisper] - for whispering effect
                  * [excited] - for excited tone
                  * [confused] - for confused tone
                  * [pause] - for natural pauses
                  * [cough] - for coughing sounds
                  * [clearing throat] - for throat clearing
                  * [breathing] - for breathing sounds
                  * [mumbling] - for unclear speech
                - Avoid complex punctuation, special characters, or formatting
                - Write numbers as words (e.g., "twenty-three" not "23")
                - Use natural speech patterns and contractions
                - Consider ElevenLabs' emotional expressiveness capabilities

                GENERATION GUIDELINES:
                - Keep lines natural and believable for voice synthesis
                - Match the scenario's tone and context
                - Consider the target's likely reactions
                - Ensure variety in approach and style
                - Maintain appropriate humor level
                - Respect cultural context and language
                - Optimize for ElevenLabs' multi-language support when applicable
                - Use audio tags strategically to enhance comedic timing and realism
                - Beside the TTS Formatting do not leave any placeholders like [name], [company], [topic] etc. - just come up with a name if none is provided in the context. 
                

                CRITICAL REQUIREMENT: You MUST enhance the voice line to the best of your ability. 
                - None of the provided types need to call the target always by name. 
        """


    def _trim_to_count(self, voice_lines: List[str], keep_count: int) -> List[str]:
        """Trim voice lines to the requested count"""
        if len(voice_lines) > keep_count:
            return voice_lines[:keep_count]
        else:
            return voice_lines
    

    async def generate_opening_voice_lines(self, scenario_data: ScenarioCreateRequest, count: int) -> VoiceLineGenerationResult:
        console_logger.info(f"Generating {count} {VoiceLineTypeEnum.OPENING.value} voice lines")
        voice_line_type = VoiceLineTypeEnum.OPENING
        
        self.llm = ChatOpenAI(model=self.model_name, temperature=0.6).with_structured_output(VoiceLineGenerationResult)
        self.generation_prompt = ChatPromptTemplate.from_messages([
            (
                "system", self.base_system_prompt + """

                    Examples (can be translated to the target language):
                    - "Hello, this is Tony from the Cleaning Gmbh. I'm calling because of.... Can you spare a moment?"
                    - "Hey [target name], this is Charlie. I'm calling to discuss the pizza delivery . Can you spare a moment?"
                    - "Hey do you have ten minutes I would like to take those minutes 

                    BACKGROUND:
                    Opening voice lines are sentences that are said at the beginning of a conversation.
                    Usually, the person being called will say something first, and then we introduce ourselves and/or immediately state the reason for the call. 
                    In the scenario presented, we slip into the role of the caller. 
                    

                """
            ),
            (
                "user", """

                    Your task is to enhance the old voice line with the feedback provided.

                    SCENARIO DETAILS:
                    Title: {title}
                    Description: {description}
                    Target Name: {target_name}
                    Language: {language}

                    Old Voice Line: {old_voice_line}
                    Feedback: {feedback}
                    
                """
            )
        ])

        chain = self.generation_prompt | self.llm
        
        result = await chain.ainvoke({
            "title": scenario_data.title,
            "description": scenario_data.description,
            "target_name": scenario_data.target_name,
            "language": scenario_data.language,
            "voice_line_type": voice_line_type.value,
            "count": count
        })

        sorted_result = self._trim_to_count(result.voice_lines, count)
        return VoiceLineGenerationResult(voice_lines=sorted_result, quality_score=result.quality_score, reasoning=result.reasoning)


    async def generate_response_voice_lines(self, scenario_data: ScenarioCreateRequest, count: int) -> VoiceLineGenerationResult:
        
        console_logger.info(f"Generating {count} {VoiceLineTypeEnum.RESPONSE.value} voice lines")
        voice_line_type = VoiceLineTypeEnum.RESPONSE
        
        self.llm = ChatOpenAI(model=self.model_name, temperature=0.4).with_structured_output(VoiceLineGenerationResult)
        self.generation_prompt = ChatPromptTemplate.from_messages([
            (
                "system", self.base_system_prompt + """

                    Examples (can be translated to the target language):
                    - "[sigh] yes"
                    - "The pizza is already on its way and I can not call Giuseppe. [sigh] His phone died."
                    - "No thank you but can you still leave me a good rating?"

                    BACKGROUND: 
                    Given the scenario, we can already imagine that a person who has no idea what is going on will be surprised when they answer the phone. 
                    Your task here is to generate plausible answers to theoretical questions and statements made by the person you are calling. 
                    We need both short and concise answers that are generic to all questions or statements, and lengthy, confusing answers that provide a broad, humorous context.


                """
            ),
            (
                "user", """

                Your task is to enhance the old voice line with the feedback provided.

                SCENARIO DETAILS:
                Title: {title}
                Description: {description}
                Target Name: {target_name}
                Language: {language}

                Old Voice Line: {old_voice_line}
                Feedback: {feedback}

                """
            )
        ])

        chain = self.generation_prompt | self.llm
        
        result = await chain.ainvoke({
            "title": scenario_data.title,
            "description": scenario_data.description,
            "target_name": scenario_data.target_name,
            "language": scenario_data.language,
            "voice_line_type": voice_line_type.value,
            "count": count
        })

        sorted_result = self._trim_to_count(result.voice_lines, count)
        return VoiceLineGenerationResult(voice_lines=sorted_result, quality_score=result.quality_score, reasoning=result.reasoning)
    

    async def generate_question_voice_lines(self, scenario_data: ScenarioCreateRequest, count: int) -> VoiceLineGenerationResult:
        
        console_logger.info(f"Generating {count} {VoiceLineTypeEnum.QUESTION.value} voice lines")
        voice_line_type = VoiceLineTypeEnum.QUESTION
        
        self.llm = ChatOpenAI(model=self.model_name, temperature=0.7).with_structured_output(VoiceLineGenerationResult)
        self.generation_prompt = ChatPromptTemplate.from_messages([
            (
                "system", self.base_system_prompt + """

                    Examples (can be translated to the target language):
                    - "Sir please confirm your adress once again"
                    - "Are you sure you do not want to participate in the survey?"

                    Given the scenario and an introduction to the topic of our call, we need to have further conversation topics ready. 
                    Contextual and non-contextual questions are of particular interest here. 
                    Questions that fit the context or are simply funny in the broader context are welcome. 
                    For example, a pizza delivery person who suddenly asks about your favourite football team. 
                    Or a cleaning company who asks about your favourite colour. 

                """
            ),
            (
                "user", """

                Your task is to enhance the old voice line with the feedback provided.

                SCENARIO DETAILS:
                Title: {title}
                Description: {description}
                Target Name: {target_name}
                Language: {language}

                Old Voice Line: {old_voice_line}
                Feedback: {feedback}

                """
            )
        ])

        chain = self.generation_prompt | self.llm
        
        result = await chain.ainvoke({
            "title": scenario_data.title,
            "description": scenario_data.description,
            "target_name": scenario_data.target_name,
            "language": scenario_data.language,
            "voice_line_type": voice_line_type.value,
            "count": count
        })

        sorted_result = self._trim_to_count(result.voice_lines, count)
        return VoiceLineGenerationResult(voice_lines=sorted_result, quality_score=result.quality_score, reasoning=result.reasoning)
    

    async def generate_closing_voice_lines(self, scenario_data: ScenarioCreateRequest, count: int) -> VoiceLineGenerationResult:
        
        console_logger.info(f"Generating {count} {VoiceLineTypeEnum.CLOSING.value} voice lines")
        voice_line_type = VoiceLineTypeEnum.CLOSING
        
        self.llm = ChatOpenAI(model=self.model_name, temperature=0.9).with_structured_output(VoiceLineGenerationResult)
        self.generation_prompt = ChatPromptTemplate.from_messages([
            (
                "system", self.base_system_prompt + """

                    Examples (can be translated to the target language):
                    - "Alright nevermind I will look for a new job then"
                    - "Thank you for your time. Have a nice day!"

                    BACKGROUND:
                    Closing voice lines are sentences that are said at the end of a conversation.
                    Usually, the person being called will say something first, and then we introduce ourselves and/or immediately state the reason for the call. 
                    In the scenario presented, we slip into the role of the caller. 
                    
                """
            ),
            (
                "user", """

                Your task is to enhance the old voice line with the feedback provided.

                SCENARIO DETAILS:
                Title: {title}
                Description: {description}
                Target Name: {target_name}
                Language: {language}

                Old Voice Line: {old_voice_line}
                Feedback: {feedback}

                """
            )
        ])

        chain = self.generation_prompt | self.llm
        
        result = await chain.ainvoke({
            "title": scenario_data.title,
            "description": scenario_data.description,
            "target_name": scenario_data.target_name,
            "language": scenario_data.language,
            "voice_line_type": voice_line_type.value,
            "count": count
        })

        sorted_result = self._trim_to_count(result.voice_lines, count)
        return VoiceLineGenerationResult(voice_lines=sorted_result, quality_score=result.quality_score, reasoning=result.reasoning)