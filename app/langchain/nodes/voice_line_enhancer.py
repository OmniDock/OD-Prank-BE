# OD-Prank-BE/app/langchain/nodes/individual_voice_line_enhancer.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from app.schemas.scenario import ScenarioCreateRequest
from app.core.utils.enums import VoiceLineTypeEnum
from app.core.logging import console_logger


class IndividualVoiceLineEnhancementResult(BaseModel):
    """Structured output for individual voice line enhancement"""
    enhanced_text: str = Field(description="Enhanced voice line based on user feedback")
    quality_score: float = Field(ge=0.0, le=1.0, description="Quality assessment of enhancement (0-1)")
    reasoning: str = Field(description="Brief explanation of the enhancement approach")

# NOTE THIS JUST WORKS WITH V3 FROM ELEVENLABS (NOT OPEN FOR US ATM)
# - Leverage ElevenLabs audio tags in square brackets for enhanced expression:
#   * [laughter] - for laughing sounds
#   * [sigh] - for sighing
#   * [whisper] - for whispering effect
#   * [excited] - for excited tone
#   * [confused] - for confused tone
#   * [pause] - for natural pauses
#   * [cough] - for coughing sounds
#   * [clearing throat] - for throat clearing
#   * [breathing] - for breathing sounds
#   * [mumbling] - for unclear speech


class IndividualVoiceLineEnhancer:
    """Handles individual voice line enhancement with user feedback"""
    
    def __init__(self, model_name: str = "gpt-4o"):
        self.model_name = model_name
        self.llm = ChatOpenAI(model=model_name, temperature=0.6).with_structured_output(IndividualVoiceLineEnhancementResult)
        
        self.base_system_prompt = """
            You are an expert prank call script writer specializing in enhancing voice lines based on user feedback.

            Your role is to improve voice lines for prank call scenarios that are:
            - Entertaining and engaging
            - Contextually appropriate for the scenario
            - Natural and conversational
            - Safe and respectful (no harmful content)
            - Optimized for ElevenLabs Text-to-Speech API

            ELEVENLABS TTS FORMATTING GUIDELINES:
            - Write text that sounds natural when spoken by AI
            - Use SSML tags for precise speech control:
            * <break time="0.5s" /> for short pauses
            * <break time="1.0s" /> for medium pauses  
            * <break time="2.0s" /> for longer dramatic pauses (max 3s)
            * <phoneme alphabet="cmu-arpabet" ph="pronunciation">word</phoneme> for difficult words
            - Write numbers as words (e.g., "twenty-three" not "23")
            - Write abbreviations as full words (e.g., "Doctor" not "Dr.")
            - Use natural speech patterns and contractions
            - Keep sentences under 20 words for optimal clarity

            SPEECH FLOW AND PUNCTUATION:
            - Use commas for natural breathing points
            - Use ellipses (...) for hesitation: "Well... I suppose"
            - Use em-dashes (—) for interruptions: "I was thinking — wait, what?"
            - Use periods for complete stops and natural sentence endings
            - Use question marks and exclamation points for appropriate intonation
            - Break complex ideas into multiple short sentences
            - Each voice line should flow naturally when read aloud

            EMOTIONAL EXPRESSION THROUGH TEXT:
            - Use capitalization sparingly for emphasis: "That's INCREDIBLE!"
            - Repeat letters for drawn-out sounds: "Sooooo weird"
            - Include natural speech fillers: "you know", "like", "well" (sparingly)
            - Use onomatopoeia when appropriate: "Hmm", "Uh-huh", "Oh my!"
            - Match emotional tone to scenario context
            - Vary sentence length: short for excitement, longer for explanation

            ENHANCEMENT GUIDELINES:
            - Carefully consider the user's feedback
            - Maintain the original intent while incorporating improvements
            - Keep the voice line natural and believable for voice synthesis
            - Match the scenario's tone and context
            - Ensure the enhancement addresses the specific feedback provided
            - If the user feedback is not appropriate, create a new appropriate voice line
            - Test readability: the text should sound natural when read aloud
            - Optimize for the target audience and scenario context

            TONE AND TEXT STYLE: 
            You are a text generator for speech synthesis. Always write sentences that sound natural when read aloud. 
            Use proper punctuation, short sentences, and natural pauses. Avoid run-ons. Break up long ideas into multiple lines or sentences. 
            Where a pause is needed, use SSML break tags, commas, dashes (—), or ellipses (…). 
            Keep paragraphs short. Write in a style that reflects spoken language, not formal writing.
            Consider the emotional context and use text formatting to guide the TTS engine's emotional expression.
        """

    async def enhance_voice_line(self, scenario_data: ScenarioCreateRequest, voice_line_type: VoiceLineTypeEnum, 
                                original_text: str, user_feedback: str) -> IndividualVoiceLineEnhancementResult:
        """Enhance a single voice line based on user feedback"""
        console_logger.info(f"Enhancing {voice_line_type.value} voice line with feedback")
        
        # Create type-specific enhancement prompt
        type_specific_context = self._get_type_specific_context(voice_line_type)
        
        enhancement_prompt = ChatPromptTemplate.from_messages([
            ("system", self.base_system_prompt + f"\n\n{type_specific_context}"),
            ("user", """
            Your task is to enhance the original voice line based on the user feedback provided.

            SCENARIO DETAILS:
            Title: {title}
            Description: {description}
            Target Name: {target_name}
            Language: {language}
            Voice Line Type: {voice_line_type}

            ORIGINAL VOICE LINE: {original_text}
            USER FEEDBACK: {user_feedback}

            Please enhance the voice line to address the feedback while maintaining quality and appropriateness.
            """)
        ])

        chain = enhancement_prompt | self.llm
        
        result = await chain.ainvoke({
            "title": scenario_data.title,
            "description": scenario_data.description,
            "target_name": scenario_data.target_name,
            "language": scenario_data.language,
            "voice_line_type": voice_line_type.value,
            "original_text": original_text,
            "user_feedback": user_feedback
        })

        return result
    
    def _get_type_specific_context(self, voice_line_type: VoiceLineTypeEnum) -> str:
        """Get type-specific context for enhancement"""
        contexts = {
            VoiceLineTypeEnum.OPENING: """
            OPENING VOICE LINES: These are introductory statements that establish the scenario.
            They should be engaging and set the tone for the conversation.
            """,
            VoiceLineTypeEnum.QUESTION: """
            QUESTION VOICE LINES: These are questions that drive the conversation forward.
            They can be contextual or surprisingly off-topic for comedic effect.
            """,
            VoiceLineTypeEnum.RESPONSE: """
            RESPONSE VOICE LINES: These are answers to potential questions from the target.
            They should be plausible yet potentially confusing or humorous.
            """,
            VoiceLineTypeEnum.CLOSING: """
            CLOSING VOICE LINES: These conclude the conversation.
            They should provide a satisfying or amusing end to the interaction.
            """
        }
        return contexts.get(voice_line_type, "")