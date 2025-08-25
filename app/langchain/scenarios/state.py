from typing import List, Dict, Annotated, Optional, TYPE_CHECKING
from typing_extensions import Literal
from pydantic import BaseModel, Field
from operator import add
from app.schemas.scenario import ScenarioCreateRequest
from app.core.utils.enums import VoiceLineTypeEnum


# New Operator for Pydantic 
def extend_list(existing: List, new: List) -> List:
    """Custom reducer to extend a list with new elements"""
    if not existing:
        return new
    if not new:
        return existing
    return existing + new


    

class SafetyCheckResult(BaseModel):
    """Structured output for safety checks"""
    is_safe: bool = Field(description="Whether the content is safe")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in safety assessment (0-1)")
    severity: Literal["low", "medium", "high", "critical"] = Field(description="Risk severity level")
    issues: List[str] = Field(description="List of specific safety concerns found")
    categories: List[
        Literal[
            "harassment", "illegal", "harmful_targeting", "excessive_cruelty",
            "privacy_violation", "discrimination", "offensive_language"]
        ] = Field(description="Categories of safety issues identified")
    recommendation: Literal["allow", "review", "modify", "reject"] = Field(description="Recommended action")
    reasoning: str = Field(description="Brief explanation of the safety assessment")


class ScenarioAnalysisResult(BaseModel):
    """Structured output for scenario analysis and persona generation"""
    persona_name: str = Field(description="Character name for the caller (e.g., 'Giuseppe', 'Müller')")
    persona_background: str = Field(description="Brief character background and motivation")
    company_service: str = Field(description="Realistic company/service the character represents if needed else something that fits the scenario")
    speech_patterns: List[str] = Field(description="List of characteristic speech patterns for this persona")
    emotional_state: str = Field(description="Current emotional state and energy level")
    conversation_goals: List[str] = Field(description="What the character wants to achieve in the call")
    believability_anchors: List[str] = Field(description="Specific details that make the scenario believable")
    absurdity_escalation: List[str] = Field(description="Progression of how absurdity should be introduced")
    cultural_context: str = Field(description="Cultural and linguistic context for the target language")
    quality_score: float = Field(ge=0.0, le=1.0, description="Quality assessment of the analysis (0-1)")
    optimized_scenario: str = Field(description="Optimized scenario with the character persona and context for guidance")


class VoiceLineState(BaseModel):
    """State object for individual voice line"""
    text: str
    type: VoiceLineTypeEnum



class ScenarioProcessorState(BaseModel):
    """State object passed between nodes in the workflow"""
    # Required fields
    scenario_data: ScenarioCreateRequest
    target_counts: Dict[VoiceLineTypeEnum, int]
    
    # Initial safety check (with defaults)
    initial_safety_check: Optional[SafetyCheckResult] = None
    overall_safety_check: Optional[SafetyCheckResult] = None
    
    # Scenario analysis (shared across all nodes)
    scenario_analysis: Optional[ScenarioAnalysisResult] = None
    
    # Generated voice lines (multiple per type) - use extend_list to extend with new voice lines
    opening_voice_lines: Annotated[List[VoiceLineState], extend_list] = Field(default_factory=list)
    question_voice_lines: Annotated[List[VoiceLineState], extend_list] = Field(default_factory=list)
    response_voice_lines: Annotated[List[VoiceLineState], extend_list] = Field(default_factory=list)
    closing_voice_lines: Annotated[List[VoiceLineState], extend_list] = Field(default_factory=list)
    
    class Config:
        """Pydantic configuration"""
        arbitrary_types_allowed = True  
        use_enum_values = True  




class IndividualVoiceLineEnhancementState(BaseModel):
    """State object for individual voice line enhancement with user feedback"""
    # Input data
    voice_line_id: int
    original_text: str
    user_feedback: str
    scenario_data: ScenarioCreateRequest
    voice_line_type: VoiceLineTypeEnum
    
    # Scenario analysis (shared context)
    scenario_analysis: Optional["ScenarioAnalysisResult"] = None
    
    # Processing results
    enhanced_text: str = ""
    safety_passed: bool = False
    safety_issues: Annotated[List[str], add] = Field(default_factory=list)
    enhancement_attempt: int = 0
    processing_complete: bool = False
    
    class Config:
        """Pydantic configuration"""
        arbitrary_types_allowed = True
        use_enum_values = True

