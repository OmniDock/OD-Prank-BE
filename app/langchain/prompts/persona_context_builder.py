from app.langchain.scenarios.state import ScenarioAnalysisResult, VoiceLineTypeEnum
from app.core.utils.enums import LanguageEnum


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
    def build_enhanced_context(analysis: ScenarioAnalysisResult, voice_line_type: VoiceLineTypeEnum) -> str:
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
                    - Escalation path: {' → '.join(analysis.absurdity_escalation)}
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
