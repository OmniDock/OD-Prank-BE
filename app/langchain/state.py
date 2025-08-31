"""
State management for LangChain v2 pipeline
"""
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field
from app.schemas.scenario import ScenarioCreateRequest


class ScenarioAnalysis(BaseModel):
    """Analysis result from analyzer node"""
    persona_name: str
    company_service: str
    conversation_goals: List[str]
    believability_anchors: List[str]
    escalation_plan: List[str]
    cultural_context: str
    voice_hints: Optional[str] = None


class SafetyResult(BaseModel):
    """Safety check result"""
    is_safe: bool
    issues: List[str] = Field(default_factory=list)
    recommendation: Literal["allow", "modify", "review", "reject"] = "allow"
    reasoning: str = ""
    confidence: float = 1.0


class QualityResult(BaseModel):
    """Quality assessment from judge"""
    seriousness: float = Field(default=1.0, ge=0.0, le=1.0)
    believability: float = Field(default=1.0, ge=0.0, le=1.0)
    subtle_emotion: float = Field(default=0.7, ge=0.0, le=1.0)
    notes: str = ""


class ScenarioState(BaseModel):
    """Main state object for the pipeline"""
    # Input
    scenario_data: ScenarioCreateRequest
    
    # Configuration
    require_clarification: bool = True
    target_counts: Dict[str, int] = Field(default_factory=lambda: {
        "OPENING": 2,
        "QUESTION": 6,
        "RESPONSE": 6,
        "CLOSING": 2,
        "FILLER": 4
    })
    
    # Clarification flow
    clarifying_questions: List[str] = Field(default_factory=list)
    clarifications: List[str] = Field(default_factory=list)  # Simple list of answers
    
    # Processing results
    analysis: Optional[ScenarioAnalysis] = None
    
    # Generated content
    plain_lines: Dict[str, List[str]] = Field(default_factory=lambda: {
        "OPENING": [],
        "QUESTION": [],
        "RESPONSE": [],
        "CLOSING": [],
        "FILLER": []
    })
    
    tts_lines: Dict[str, List[str]] = Field(default_factory=lambda: {
        "OPENING": [],
        "QUESTION": [],
        "RESPONSE": [],
        "CLOSING": [],
        "FILLER": []
    })
    
    # Quality and safety
    quality: Optional[QualityResult] = None
    safety: Optional[SafetyResult] = None
    
    # Tracking
    was_rewritten: bool = False
    processing_complete: bool = False
    
    # Enhancement fields
    user_feedback: Optional[str] = None
    was_enhanced: bool = False
    enhancement_changes: Optional[List[str]] = None
    
    class Config:
        """Pydantic configuration"""
        arbitrary_types_allowed = True
        use_enum_values = True
