from typing import List, Dict, Annotated, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field
from operator import add
from app.schemas.scenario import ScenarioCreateRequest
from app.core.utils.enums import VoiceLineTypeEnum


def extend_list(existing: List, new: List) -> List:
    """Custom reducer to extend a list with new elements"""
    if not existing:
        return new
    if not new:
        return existing
    return existing + new

class ScenarioAnalysisResult(BaseModel):
    """Structured output for scenario analysis and persona generation"""
    persona_name: str = Field(description="Character name for the caller (e.g., 'Giuseppe', 'Müller')")
    persona_background: str = Field(description="Brief character background and motivation")
    company_service: str = Field(description="Realistic company/service the character represents")
    speech_patterns: List[str] = Field(description="List of characteristic speech patterns for this persona")
    emotional_state: str = Field(description="Current emotional state and energy level")
    conversation_goals: List[str] = Field(description="What the character wants to achieve in the call")
    believability_anchors: List[str] = Field(description="Specific details that make the scenario believable")
    absurdity_escalation: List[str] = Field(description="Progression of how absurdity should be introduced")
    cultural_context: str = Field(description="Cultural and linguistic context for the target language")
    quality_score: float = Field(ge=0.0, le=1.0, description="Quality assessment of the analysis (0-1)")



class VoiceLineState(BaseModel):
    """State object for individual voice line"""
    text: str
    type: VoiceLineTypeEnum
    generation_attempt: int = 1
    #safety_passed: bool = False
    #safety_issues: Annotated[List[str], add] = Field(default_factory=list)  # Append new issues
    #diversity_score: float = 0.0
    



class ScenarioProcessorState(BaseModel):
    """State object passed between nodes in the workflow"""
    # Required fields
    scenario_data: ScenarioCreateRequest
    target_counts: Dict[VoiceLineTypeEnum, int]
    
    # Initial safety check (with defaults)
    initial_safety_passed: bool = False
    initial_safety_issues: Annotated[List[str], add] = Field(default_factory=list) 
    initial_safety_attempts: int = 0
    
    # Scenario analysis (shared across all nodes)
    scenario_analysis: Optional[ScenarioAnalysisResult] = None
    
    # Generated voice lines (multiple per type) - use extend_list to extend with new voice lines
    opening_voice_lines: Annotated[List[VoiceLineState], extend_list] = Field(default_factory=list)
    question_voice_lines: Annotated[List[VoiceLineState], extend_list] = Field(default_factory=list)
    response_voice_lines: Annotated[List[VoiceLineState], extend_list] = Field(default_factory=list)
    closing_voice_lines: Annotated[List[VoiceLineState], extend_list] = Field(default_factory=list)
    
    # Diversity check status
    #opening_diversity_passed: bool = False
    #question_diversity_passed: bool = False
    #response_diversity_passed: bool = False
    #closing_diversity_passed: bool = False
    
    # Retry attempt counters
    #opening_generation_attempts: int = 0
    #question_generation_attempts: int = 0
    #response_generation_attempts: int = 0
    #closing_generation_attempts: int = 0

    #opening_diversity_attempts: int = 0
    #question_diversity_attempts: int = 0
    #response_diversity_attempts: int = 0
    #closing_diversity_attempts: int = 0
    
    # Individual safety status
    #opening_safety_passed: bool = False
    #question_safety_passed: bool = False
    #response_safety_passed: bool = False
    #closing_safety_passed: bool = False
    
    # Overall results
    overall_safety_passed: bool = False
    overall_safety_issues: Annotated[List[str], add] = Field(default_factory=list) 
    overall_diversity_passed: bool = False
    processing_complete: bool = False

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

