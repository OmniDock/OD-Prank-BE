from typing import List, Dict, Annotated
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

